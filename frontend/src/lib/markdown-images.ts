export interface MarkdownImageAttachment {
  key: string;
  src: string;
  alt: string;
  raw: string;
}

function findUnescapedClosingBracket(value: string, start: number) {
  let depth = 0;

  for (let index = start; index < value.length; index += 1) {
    if (value[index] === "\\") {
      index += 1;
      continue;
    }
    if (value[index] === "[") {
      depth += 1;
    } else if (value[index] === "]") {
      if (depth === 0) return index;
      depth -= 1;
    }
  }

  return -1;
}

function findClosingImageParenthesis(value: string, start: number) {
  let depth = 1;

  for (let index = start; index < value.length; index += 1) {
    if (value[index] === "\\") {
      index += 1;
      continue;
    }
    if (value[index] === "(") {
      depth += 1;
    } else if (value[index] === ")") {
      depth -= 1;
      if (depth === 0) return index;
    }
  }

  return -1;
}

function getImageSource(imageBody: string) {
  const trimmed = imageBody.trim();
  if (!trimmed) return "";

  if (trimmed.startsWith("<")) {
    const closingIndex = trimmed.indexOf(">");
    return closingIndex > 0 ? trimmed.slice(1, closingIndex) : "";
  }

  let depth = 0;
  for (let index = 0; index < trimmed.length; index += 1) {
    const character = trimmed[index];
    if (character === "\\") {
      index += 1;
      continue;
    }
    if (character === "(") depth += 1;
    if (character === ")") depth -= 1;
    if (/\s/.test(character) && depth === 0) {
      return trimmed.slice(0, index);
    }
  }

  return trimmed;
}

function parseMarkdownImage(value: string, start: number) {
  if (!value.startsWith("![", start)) return null;

  const altEnd = findUnescapedClosingBracket(value, start + 2);
  if (altEnd < 0 || value[altEnd + 1] !== "(") return null;

  const imageEnd = findClosingImageParenthesis(value, altEnd + 2);
  if (imageEnd < 0) return null;

  const src = getImageSource(value.slice(altEnd + 2, imageEnd));
  if (!src) return null;

  return {
    alt: value.slice(start + 2, altEnd),
    end: imageEnd + 1,
    raw: value.slice(start, imageEnd + 1),
    src,
  };
}

function isClosingFenceLine(line: string, openingDelimiter: string) {
  const fenceMatch = line.match(/^ {0,3}(`{3,}|~{3,})/);
  if (
    !fenceMatch ||
    fenceMatch[1][0] !== openingDelimiter[0] ||
    fenceMatch[1].length < openingDelimiter.length
  ) {
    return false;
  }

  return /^[ \t]*(?:\r?\n)?$/.test(line.slice(fenceMatch[0].length));
}

export function extractMarkdownImageAttachments(
  content: string,
  imageSourceMap?: Record<string, string>,
) {
  const images: MarkdownImageAttachment[] = [];
  let text = "";
  let index = 0;
  let fencedCodeDelimiter: string | null = null;

  while (index < content.length) {
    const lineEnd = content.indexOf("\n", index);
    const nextLineIndex = lineEnd < 0 ? content.length : lineEnd + 1;
    const line = content.slice(index, nextLineIndex);
    const fenceMatch = line.match(/^ {0,3}(`{3,}|~{3,})/);

    if (fencedCodeDelimiter) {
      text += line;
      if (isClosingFenceLine(line, fencedCodeDelimiter)) {
        fencedCodeDelimiter = null;
      }
      index = nextLineIndex;
      continue;
    }

    if (fenceMatch) {
      fencedCodeDelimiter = fenceMatch[1];
      text += line;
      index = nextLineIndex;
      continue;
    }

    let lineIndex = 0;
    while (lineIndex < line.length) {
      if (line[lineIndex] === "\\") {
        text += line.slice(lineIndex, lineIndex + 2);
        lineIndex += 2;
        continue;
      }

      if (line[lineIndex] === "`") {
        const run = line.slice(lineIndex).match(/^`+/)?.[0] ?? "`";
        const closingIndex = line.indexOf(run, lineIndex + run.length);
        if (closingIndex >= 0) {
          text += line.slice(lineIndex, closingIndex + run.length);
          lineIndex = closingIndex + run.length;
          continue;
        }
      }

      const image = parseMarkdownImage(line, lineIndex);
      if (image) {
        const resolvedSrc = imageSourceMap?.[image.src] ?? image.src;
        if (!resolvedSrc) {
          text += image.raw;
        } else {
          images.push({
            key: `${index + lineIndex}-${images.length}`,
            src: resolvedSrc,
            alt: image.alt,
            raw: image.raw,
          });
        }
        lineIndex = image.end;
        continue;
      }

      text += line[lineIndex];
      lineIndex += 1;
    }
    index = nextLineIndex;
  }

  return { images, text };
}

export function stripMarkdownImages(content: string) {
  return extractMarkdownImageAttachments(content).text.replace(/\s+/g, " ").trim();
}
