package dev.reel.websource

import org.json.JSONArray
import org.json.JSONObject
import org.jsoup.Jsoup
import org.jsoup.nodes.Document
import org.jsoup.nodes.Element
import java.net.URI
import java.util.Locale

data class Media(val url: String, val label: String, val referer: String)
data class Entry(val url: String, val title: String, val poster: String? = null)
data class Page(val url: String, val html: String, val direct: Boolean = false, val referer: String? = null)

class Rules(val json: JSONObject) {
    fun text(key: String, fallback: String = "") = json.optString(key, fallback).trim()
    fun flag(key: String, fallback: Boolean = false) = json.optBoolean(key, fallback)
    fun depth() = json.optInt("maxIframeDepth", 2).coerceIn(0, 3)
    fun hosts(): Set<String> {
        val array = json.optJSONArray("iframeHosts") ?: return emptySet()
        return (0 until array.length()).map { array.getString(it).lowercase(Locale.ROOT) }.toSet()
    }
}

object Parser {
    private val mediaExtension = Regex("\\.(mp4|m4v|mkv|m3u8|webm|mov|ogv)$", RegexOption.IGNORE_CASE)
    private val quotedMedia = Regex("[\"']([^\"'\\s]+?\\.(?:mp4|m4v|mkv|m3u8|webm|mov|ogv)(?:\\?[^\"'\\s]*)?)[\"']", RegexOption.IGNORE_CASE)

    fun url(raw: String, base: String? = null): String? = runCatching {
        if (raw.length > 8192 || raw.isBlank()) return null
        val cleaned = raw.trim().replace("\\/", "/").replace("\\u0026", "&").replace("\\u003d", "=").replace("\\u003D", "=").replace(" ", "%20")
        val uri = (if (base != null) URI(base).resolve(cleaned) else URI(cleaned)).normalize()
        val host = uri.host?.lowercase(Locale.ROOT)?.trimEnd('.') ?: return null
        if (uri.scheme != "https" || uri.userInfo != null || uri.port !in listOf(-1, 443)) return null
        if (!host.contains('.') || host.contains(':') || host.endsWith(".local") || host.endsWith(".internal") || host.endsWith(".localhost")) return null
        val ip = host.split('.').map { it.toIntOrNull() }
        if (ip.size == 4 && ip.all { it != null }) {
            val a = ip[0]!!; val b = ip[1]!!
            if (ip.any { it!! !in 0..255 } || a == 0 || a == 10 || a == 127 || a >= 224 ||
                (a == 169 && b == 254) || (a == 172 && b in 16..31) || (a == 192 && b == 168) || (a == 100 && b in 64..127)) return null
        }
        uri.toASCIIString().substringBefore('#')
    }.getOrNull()

    fun isMedia(url: String) = runCatching { mediaExtension.containsMatchIn(URI(url).path) }.getOrDefault(false)
    fun document(page: Page): Document = Jsoup.parse(page.html, page.url)
    fun base(doc: Document, page: Page): String = doc.selectFirst("base[href]")?.attr("href")?.let { url(it, page.url) } ?: page.url
    fun pick(root: Element, selector: String): Element? = if (selector.isBlank()) root else root.selectFirst(selector)
    fun link(node: Element, base: String): String? = sequenceOf("href", "data-href", "src", "data-src").mapNotNull { url(node.attr(it), base) }.firstOrNull()
    fun label(node: Element, fallback: String): String = (node.attr("title").ifBlank { node.text() }).trim().take(180).ifBlank { fallback }

    fun entries(page: Page, rules: Rules): List<Entry> {
        val doc = document(page); val base = base(doc, page)
        val selector = rules.text("itemSelector")
        require(selector.isNotBlank()) { "Set itemSelector in this website's rules to enable catalogue browsing." }
        return doc.select(selector).take(200).mapNotNull { item ->
            val anchor = pick(item, rules.text("linkSelector")) ?: return@mapNotNull null
            val target = link(anchor, base) ?: return@mapNotNull null
            val title = pick(item, rules.text("titleSelector"))?.let { label(it, target) } ?: label(anchor, target)
            val img = pick(item, rules.text("posterSelector", "img"))
            val poster = img?.let { url(it.attr(rules.text("posterAttribute", "src")), base) }
            Entry(target, title, poster)
        }.distinctBy { it.url }
    }

    fun media(page: Page, rules: Rules): List<Media> {
        if (page.direct || isMedia(page.url)) return listOf(Media(page.url, "Direct video", page.referer ?: page.url))
        val doc = document(page); val base = base(doc, page); val found = linkedMapOf<String, Media>()
        fun add(raw: String, label: String = "Video", force: Boolean = false) {
            if (found.size >= 100) return
            val target = url(raw, base) ?: return
            if (!force && !isMedia(target)) return
            found.putIfAbsent(target, Media(target, label.ifBlank { "Video" }.take(120), page.url))
        }
        doc.select("video, video source").forEach { node ->
            listOf("src", "data-src", "data-video", "data-url").forEach { attr -> add(node.attr(attr), node.attr("label").ifBlank { node.attr("data-quality") }, true) }
        }
        doc.select("a[href]").forEach { add(it.attr("href"), label(it, "Video")) }
        doc.select("meta[property=og:video],meta[property=og:video:url],meta[property=og:video:secure_url],meta[name=twitter:player:stream]").forEach { add(it.attr("content"), "Embedded video") }
        val selector = rules.text("videoSelector")
        if (selector.isNotBlank()) doc.select(selector).forEach { add(it.attr(rules.text("videoAttribute", "src")), "Configured source", true) }
        fun jsonMedia(value: Any?, depth: Int = 0) {
            if (depth > 15) return
            when (value) {
                is JSONObject -> {
                    if (value.optString("@type").contains("VideoObject")) add(value.optString("contentUrl"), value.optString("name", "Video"), true)
                    value.keys().forEach { jsonMedia(value.opt(it), depth + 1) }
                }
                is JSONArray -> (0 until value.length()).forEach { jsonMedia(value.opt(it), depth + 1) }
            }
        }
        doc.select("script[type=application/ld+json]").forEach { runCatching { val raw = it.data().trim(); jsonMedia(if (raw.startsWith("[")) JSONArray(raw) else JSONObject(raw)) } }
        if (rules.flag("scanScriptUrls", true)) doc.select("script").forEach { node ->
            val text = node.data().replace("\\/", "/").replace("\\u0026", "&")
            quotedMedia.findAll(text).take(100).forEach { add(it.groupValues[1], "Embedded URL") }
        }
        return found.values.toList()
    }

    fun frames(page: Page, rules: Rules): List<String> {
        val doc = document(page); val base = base(doc, page)
        val allowed = rules.hosts() + URI(page.url).host.lowercase(Locale.ROOT)
        return doc.select(rules.text("iframeSelector", "iframe[src],iframe[data-src]")).mapNotNull { node ->
            val target = url(node.attr("src").ifBlank { node.attr("data-src") }, base) ?: return@mapNotNull null
            if (URI(target).host.lowercase(Locale.ROOT) in allowed) target else null
        }.distinct().take(5)
    }
}
