package dev.reel.websource

import android.util.Base64
import eu.kanade.tachiyomi.animesource.model.AnimeFilterList
import eu.kanade.tachiyomi.animesource.model.AnimesPage
import eu.kanade.tachiyomi.animesource.model.Hoster
import eu.kanade.tachiyomi.animesource.model.SAnime
import eu.kanade.tachiyomi.animesource.model.SAnimeEpisodeUpdate
import eu.kanade.tachiyomi.animesource.model.SEpisode
import eu.kanade.tachiyomi.animesource.model.Video
import eu.kanade.tachiyomi.animesource.online.AnimeHttpSource
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import okhttp3.CookieJar
import okhttp3.Dns
import okhttp3.Headers
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.net.URI
import java.net.URLEncoder
import java.net.UnknownHostException
import java.util.concurrent.TimeUnit
import kotlin.coroutines.coroutineContext

open class WebSiteSource(encoded: String) : AnimeHttpSource() {
    private val config = JSONObject(String(Base64.decode(encoded, Base64.DEFAULT), Charsets.UTF_8))
    private val rules = Rules(config.optJSONObject("rules") ?: JSONObject())
    private val startUrl = config.getString("url")
    override val name = config.getString("name")
    override val lang = config.getString("language")
    override val id = config.getString("sourceId").toLong()
    override val baseUrl = "https://" + URI(startUrl).rawAuthority
    override val supportsLatest = rules.text("latestPath").isNotBlank()
    override val supportsRelatedAnime = false

    override val client: OkHttpClient by lazy {
        super.client.newBuilder().followRedirects(false).followSslRedirects(false)
            .cookieJar(CookieJar.NO_COOKIES).callTimeout(30, TimeUnit.SECONDS)
            .dns { host ->
                Dns.SYSTEM.lookup(host).also { addresses ->
                    if (addresses.isEmpty() || addresses.any { address ->
                        address.isAnyLocalAddress || address.isLoopbackAddress || address.isLinkLocalAddress ||
                            address.isSiteLocalAddress || address.isMulticastAddress ||
                            (address.address.size == 16 && (address.address[0].toInt() and 0xfe) == 0xfc)
                    }) throw UnknownHostException("This source resolved to a non-public address.")
                }
            }.build()
    }

    private fun requestHeaders(referer: String? = null): Headers {
        val builder = headers.newBuilder()
        rules.json.optJSONObject("extraHeaders")?.let { extra -> extra.keys().forEach { builder.set(it, extra.getString(it)) } }
        if (referer != null && rules.flag("sendReferer", true)) builder.set("Referer", referer)
        return builder.build()
    }

    private suspend fun page(raw: String, referer: String? = null): Page = withContext(Dispatchers.IO) {
        var target = Parser.url(raw, startUrl) ?: throw IOException("Only public HTTPS sources are supported.")
        if (Parser.isMedia(target)) return@withContext Page(target, "", true, referer)
        repeat(6) {
            coroutineContext.ensureActive()
            client.newCall(Request.Builder().url(target).headers(requestHeaders(referer)).build()).execute().use { response ->
                if (response.code in listOf(301, 302, 303, 307, 308)) {
                    target = response.header("Location")?.let { Parser.url(it, target) } ?: throw IOException("Unsafe or invalid redirect.")
                } else {
                    if (!response.isSuccessful) throw IOException("Website returned HTTP ${response.code}. Login and access restrictions are not bypassed.")
                    val mime = response.header("Content-Type").orEmpty()
                    if (mime.startsWith("video/", true) || mime.contains("mpegurl", true)) return@withContext Page(target, "", true, referer)
                    val body = response.body
                    if (body.contentLength() > 4 * 1024 * 1024) throw IOException("Page exceeds the 4 MiB scan limit.")
                    val output = ByteArrayOutputStream()
                    val block = ByteArray(8192)
                    body.byteStream().use { input ->
                        while (true) {
                            coroutineContext.ensureActive()
                            val size = input.read(block)
                            if (size < 0) break
                            if (output.size() + size > 4 * 1024 * 1024) throw IOException("Page exceeds the 4 MiB scan limit.")
                            output.write(block, 0, size)
                        }
                    }
                    return@withContext Page(target, output.toString(body.contentType()?.charset(Charsets.UTF_8)?.name() ?: "UTF-8"))
                }
            }
        }
        throw IOException("Too many redirects.")
    }

    private fun anime(entry: Entry) = SAnime.create().apply {
        url = entry.url; title = entry.title; thumbnail_url = entry.poster
    }

    private fun path(template: String, number: Int, query: String = ""): String = Parser.url(
        template.replace("{page}", number.toString()).replace("{query}", URLEncoder.encode(query, "UTF-8")),
        startUrl,
    ) ?: throw IOException("Invalid source path.")

    private suspend fun listing(template: String, number: Int, query: String = ""): AnimesPage {
        if (number > 1 && !template.contains("{page}")) return AnimesPage(emptyList(), false)
        val loaded = page(path(template, number, query))
        val entries = Parser.entries(loaded, rules)
        val nextSelector = rules.text("nextSelector")
        val hasNext = template.contains("{page}") && nextSelector.isNotBlank() && entries.isNotEmpty() &&
            Parser.document(loaded).select(nextSelector).isNotEmpty()
        return AnimesPage(entries.map(::anime), hasNext)
    }

    override suspend fun getPopularAnime(page: Int): AnimesPage {
        val catalog = rules.text("catalogPath")
        return if (catalog.isNotBlank()) listing(catalog, page)
        else AnimesPage(if (page == 1) listOf(anime(Entry(startUrl, name))) else emptyList(), false)
    }

    override suspend fun getLatestUpdates(page: Int): AnimesPage =
        if (supportsLatest) listing(rules.text("latestPath"), page) else getPopularAnime(page)

    override suspend fun getSearchAnime(page: Int, query: String, filters: AnimeFilterList): AnimesPage {
        val pasted = Parser.url(query)
        if (pasted != null) return AnimesPage(if (page == 1) listOf(anime(Entry(pasted, URI(pasted).path.substringAfterLast('/').ifBlank { URI(pasted).host }))) else emptyList(), false)
        val search = rules.text("searchPath")
        if (search.isNotBlank()) return listing(search, page, query)
        val popular = getPopularAnime(page)
        return AnimesPage(popular.animes.filter { it.title.contains(query, true) }, false)
    }

    override suspend fun getAnimeEpisodeUpdate(anime: SAnime, episodes: List<SEpisode>, fetchDetails: Boolean, fetchEpisodes: Boolean): SAnimeEpisodeUpdate {
        if (!fetchDetails && !fetchEpisodes) return SAnimeEpisodeUpdate(anime, episodes)
        val loaded = page(anime.url)
        val doc = Parser.document(loaded)
        val base = Parser.base(doc, loaded)
        val updated = SAnime.create().apply {
            url = anime.url; title = anime.title; artist = anime.artist; author = anime.author
            description = anime.description; genre = anime.genre; status = anime.status
            thumbnail_url = anime.thumbnail_url; background_url = anime.background_url
            update_strategy = anime.update_strategy; fetch_type = anime.fetch_type
            season_number = anime.season_number; memo = anime.memo; initialized = anime.initialized
        }
        if (fetchDetails) {
            val selector = rules.text("detailTitleSelector", "h1")
            val title = doc.selectFirst(selector)?.text()?.trim().orEmpty().ifBlank { doc.title() }
            if (title.isNotBlank()) updated.title = title.take(180)
            updated.description = rules.text("descriptionSelector").takeIf { it.isNotBlank() }?.let { doc.selectFirst(it)?.text() }
                ?: "Website source. You can paste a full public video-page URL into this source's search box."
            updated.thumbnail_url = doc.selectFirst("meta[property=og:image]")?.attr("content")?.let { Parser.url(it, base) } ?: updated.thumbnail_url
            updated.status = SAnime.UNKNOWN
            updated.initialized = true
        }
        val selector = rules.text("episodeSelector")
        val updatedEpisodes = if (!fetchEpisodes) episodes else if (selector.isBlank() || loaded.direct) {
            listOf(SEpisode.create().apply { url = loaded.url; name = "Play video"; episode_number = 1f })
        } else {
            val entries = doc.select(selector).take(2000).mapNotNull { element ->
                val link = Parser.pick(element, rules.text("episodeLinkSelector")) ?: return@mapNotNull null
                val target = Parser.link(link, base) ?: return@mapNotNull null
                val title = Parser.pick(element, rules.text("episodeTitleSelector"))?.let { Parser.label(it, "Episode") } ?: "Episode"
                Entry(target, title)
            }.distinctBy { it.url }
            if (entries.isEmpty()) throw IOException("No episodes match this site's episodeSelector. Update its extraction rules.")
            val chronological = if (rules.flag("episodesReversed", false)) entries.reversed() else entries
            chronological.mapIndexed { index, entry -> SEpisode.create().apply { url = entry.url; name = entry.title; episode_number = (index + 1).toFloat() } }.reversed()
        }
        return SAnimeEpisodeUpdate(updated, updatedEpisodes)
    }

    override suspend fun getHosterList(episode: SEpisode): List<Hoster> = listOf(Hoster(hosterUrl = episode.url, hosterName = name))

    override suspend fun getVideoList(hoster: Hoster): List<Video> {
        val visited = mutableSetOf<String>(); val media = linkedMapOf<String, Media>(); val failures = mutableListOf<String>()
        suspend fun visit(url: String, depth: Int, referer: String? = null) {
            if (visited.size >= 8 || !visited.add(url)) return
            val loaded = page(url, referer)
            Parser.media(loaded, rules).forEach { media.putIfAbsent(it.url, it) }
            if (depth < rules.depth()) for (frame in Parser.frames(loaded, rules)) {
                try { visit(frame, depth + 1, loaded.url) }
                catch (e: kotlinx.coroutines.CancellationException) { throw e }
                catch (e: IOException) { failures.add(e.message.orEmpty()) }
            }
        }
        visit(hoster.hosterUrl, 0)
        if (media.isEmpty()) throw IOException("No static video URL found. Configure videoSelector or allowed iframeHosts, or use a site-specific adapter. JavaScript players and DRM are unsupported." + failures.firstOrNull()?.let { " First frame error: $it" }.orEmpty())
        return media.values.map { Video(videoUrl = it.url, videoTitle = it.label, headers = requestHeaders(it.referer), initialized = true) }
    }

    override fun getAnimeUrl(anime: SAnime) = anime.url
    override fun getEpisodeUrl(episode: SEpisode) = episode.url
    override fun getHomeUrl() = startUrl
}
