import { useEffect } from "react"
import { useSiteConfig } from "@/contexts/runtime-config"

interface JsonLdProps {
  title: string
  description: string
  slug: string
  type: "posts" | "diary"
  publishedAt?: string
  tags?: string[]
}

const JsonLd = ({ title, description, slug, type, publishedAt, tags }: JsonLdProps) => {
  const site = useSiteConfig()

  useEffect(() => {
    const publisherName = site.name || site.title
    const script = document.createElement("script")
    script.type = "application/ld+json"
    script.id = "json-ld-blogposting"

    const data: Record<string, unknown> = {
      "@context": "https://schema.org",
      "@type": "BlogPosting",
      headline: title,
      description: description?.slice(0, 160) || "",
      author: {
        "@type": "Person",
        name: publisherName,
      },
      publisher: {
        "@type": "Person",
        name: publisherName,
      },
      mainEntityOfPage: {
        "@type": "WebPage",
        "@id": `${window.location.origin}/${type}/${slug}`,
      },
    }

    if (publishedAt) data.datePublished = publishedAt
    if (tags && tags.length > 0) data.keywords = tags.join(", ")

    script.textContent = JSON.stringify(data)

    const existing = document.getElementById("json-ld-blogposting")
    if (existing) existing.remove()
    document.head.appendChild(script)

    return () => {
      const el = document.getElementById("json-ld-blogposting")
      if (el) el.remove()
    }
  }, [title, description, slug, type, publishedAt, tags, site])

  return null
}

export default JsonLd
