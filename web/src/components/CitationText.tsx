// Renders text containing Venice web-search citation markers (^1^ or ^1,2^)
// as hoverable footnote links resolved against a citations array.
import { Fragment } from 'react'

export interface Citation {
  index: number
  url: string
  title: string
}

export default function CitationText({ text, citations }: { text: string; citations: Citation[] }) {
  const byIndex = new Map(citations.map((c) => [c.index, c]))
  const parts = text.split(/\^(\d+(?:,\s*\d+)*)\^/g)
  return (
    <span>
      {parts.map((part, i) => {
        if (i % 2 === 0) return <Fragment key={i}>{part}</Fragment>
        return part.split(/,\s*/).map((numStr, j) => {
          const cite = byIndex.get(Number(numStr))
          if (!cite) return <sup key={`${i}-${j}`}>{numStr}</sup>
          return (
            <sup key={`${i}-${j}`} style={{ marginLeft: 1 }}>
              <a href={cite.url} target="_blank" rel="noreferrer" title={cite.title}>
                [{numStr}]
              </a>
            </sup>
          )
        })
      })}
    </span>
  )
}
