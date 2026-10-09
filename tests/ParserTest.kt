import dev.reel.websource.*
import org.json.JSONObject

fun main(args: Array<String>) {
    var count = 0
    fun expect(value: Boolean, label: String) { check(value) { label }; println("PASS $label"); count++ }
    val rules = Rules(JSONObject())
    expect(Parser.url("../movie.mp4?x=1&y=2", "https://example.com/watch/page") == "https://example.com/movie.mp4?x=1&y=2", "relative URL and signed query")
    expect(Parser.url("//cdn.example.com/v.m3u8", "https://example.com/") == "https://cdn.example.com/v.m3u8", "protocol-relative HLS")
    listOf("javascript:alert(1)", "file:///etc/passwd", "https://127.0.0.1/a.mp4", "https://u:p@example.com/a", "https://x.local/video").forEach { expect(Parser.url(it) == null, "reject $it") }
    val page = Page("https://example.com/folder/page", """<base href="/media/"><video hidden src="a.mp4?token=x&amp;b=2"><source src="//cdn.example.com/h.m3u8"></video><a href="a.mp4?token=x&amp;b=2">duplicate</a><video data-src="lazy.webm"></video><script type="application/ld+json">{"@type":"VideoObject","contentUrl":"schema.mp4"}</script><script>var src="https:\/\/cdn.example.com\/script.mkv";</script>""")
    val media = Parser.media(page, rules)
    expect(media.size == 5, "hidden HTML5, lazy, JSON-LD, scripts and deduplication")
    expect(media.first().url == "https://example.com/media/a.mp4?token=x&b=2", "base element and entity correction")
    expect(Parser.media(Page("https://example.com/direct.mp4", "", true), rules).size == 1, "direct video")
    expect(Parser.media(Page("https://example.com/direct.mp4", "", true, "https://example.com/watch"), rules).single().referer == "https://example.com/watch", "direct iframe retains parent referer")
    val frames = Page("https://example.com/watch", """<iframe src="/embed"></iframe><iframe src="https://player.example.net/v"></iframe><iframe src="https://bad.example.net/v"></iframe>""")
    expect(Parser.frames(frames,rules) == listOf("https://example.com/embed"), "same-host frames only by default")
    expect(Parser.frames(frames,Rules(JSONObject("""{"iframeHosts":["player.example.net"]}"""))).size == 2, "explicit host allowlist")
    val catalog = Page("https://example.com/", """<article class="card"><a href="/show"><h2>One</h2><img data-src="/cover.jpg"></a></article>""")
    val entries = Parser.entries(catalog,Rules(JSONObject("""{"itemSelector":".card","linkSelector":"a","titleSelector":"h2","posterAttribute":"data-src"}""")))
    expect(entries.single() == Entry("https://example.com/show","One","https://example.com/cover.jpg"), "catalogue rules")
    expect(Parser.media(Page("https://example.com/x","""<div data-video="/v.m3u8"></div>"""),Rules(JSONObject("""{"videoSelector":"[data-video]","videoAttribute":"data-video"}"""))).single().url == "https://example.com/v.m3u8", "custom media attribute")
    args.forEach { filename ->
        val source = JSONObject(java.io.File(filename).readText())
        val configuredRules = source.optJSONObject("rules") ?: JSONObject()
        configuredRules.keys().forEach { key ->
            if (key.endsWith("Selector") && configuredRules.getString(key).isNotBlank()) {
                try { org.jsoup.Jsoup.parse("").select(configuredRules.getString(key)) }
                catch (error: IllegalArgumentException) { throw IllegalArgumentException("Invalid $key in ${source.getString("id")}: ${error.message}") }
            }
        }
        println("PASS configured selectors: ${source.getString("id")}")
    }
    println("$count Kotlin extraction checks passed.")
}
