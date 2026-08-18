import { useEffect } from "react"
import { useSiteConfig } from "@/contexts/runtime-config"
import { buildArticleStructuredData } from "@/lib/article-structured-data"

interface JsonLdProps {
  title: string
  description: string
  slug: string
  type: "posts" | "notes" | "diary"
  publishedAt?: string
  modifiedAt?: string
  tags?: string[]
}

const JsonLd = ({ title, description, slug, type, publishedAt, modifiedAt, tags }: JsonLdProps) => {
  const site = useSiteConfig()

  useEffect(() => {
    const script = document.createElement("script")
    script.type = "application/ld+json"
    script.id = "json-ld-blogposting"

    const data = buildArticleStructuredData({
      title,
      description,
      slug,
      type,
      publishedAt,
      modifiedAt,
      tags,
      image: site.shareImage || site.ogImage,
      origin: window.location.origin,
      canonicalBaseUrl: site.searchOptimization.canonicalUrl,
      siteName: site.name || site.title,
      realName: site.searchOptimization.realName,
    })

    script.textContent = JSON.stringify(data)

    const existing = document.getElementById("json-ld-blogposting")
    if (existing) existing.remove()
    document.head.appendChild(script)

    return () => {
      const el = document.getElementById("json-ld-blogposting")
      if (el) el.remove()
    }
  }, [title, description, slug, type, publishedAt, modifiedAt, tags, site])

  return null
}

export default JsonLd
