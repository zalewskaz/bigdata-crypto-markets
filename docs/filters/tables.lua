-- Table captions and cross-references that stay invisible / readable on GitHub.
--
-- Caption: an HTML comment directly after a table
--     <!-- Table: Attributes of crypto trades. {#tbl-trades} -->
-- becomes the table caption (numbered "Table N") with label tbl-trades.
--
-- Reference: a link to the table id
--     [Table](#tbl-trades) presents ...
-- becomes "Table N" in LaTeX (on GitHub it reads simply "Table").

local CAPTION = "^%s*<!%-%-%s*Table:%s*(.-)%s*{#([%w%-_:]+)}%s*%-%->%s*$"

function Blocks(blocks)
  local out = pandoc.Blocks({})
  local i = 1
  while i <= #blocks do
    local blk, nxt = blocks[i], blocks[i + 1]
    if blk.t == "Table" and nxt and nxt.t == "RawBlock" and nxt.format == "html" then
      local text, id = nxt.text:match(CAPTION)
      if text then
        local parsed = pandoc.read(text, "markdown").blocks[1]
        blk.caption = { long = { pandoc.Plain(parsed and parsed.content or {}) } }
        blk.identifier = id
        out:insert(blk)
        i = i + 2
        goto continue
      end
    end
    out:insert(blk)
    i = i + 1
    ::continue::
  end
  return out
end

-- [Figure](#fig-architecture) works the same way and becomes "Figure N".
local KINDS = { tbl = "Table", fig = "Figure" }

function Link(el)
  local id = el.target:match("^#(%a+%-[%w%-_:]+)$")
  local kind = id and id:match("^(%a+)%-")
  if kind and KINDS[kind] and FORMAT:match("latex") then
    return pandoc.RawInline("latex", KINDS[kind] .. "~\\ref{" .. id .. "}")
  end
end
