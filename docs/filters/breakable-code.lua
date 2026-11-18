-- Lets LaTeX break long inline code (e.g. TIME_SERIES_WEEKLY, /data/raw/<source>/)
-- after separator characters, so it does not overflow narrow table columns.

local escapes = {
  ["\\"] = "\\textbackslash{}", ["{"] = "\\{", ["}"] = "\\}",
  ["$"] = "\\$", ["&"] = "\\&", ["#"] = "\\#", ["%"] = "\\%",
  ["_"] = "\\_", ["^"] = "\\^{}", ["~"] = "\\textasciitilde{}",
}

local breakable = { ["_"] = true, ["/"] = true, ["-"] = true, [":"] = true,
                    ["#"] = true, ["."] = true, [","] = true }

function Code(el)
  if not FORMAT:match("latex") then return nil end
  local out = {}
  for _, cp in utf8.codes(el.text) do
    local ch = utf8.char(cp)
    table.insert(out, escapes[ch] or ch)
    if breakable[ch] then table.insert(out, "\\allowbreak{}") end
  end
  return pandoc.RawInline("latex", "\\texttt{" .. table.concat(out) .. "}")
end
