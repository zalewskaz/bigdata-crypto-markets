#!/bin/bash
# Builds the project documentation from the repository README:
#   README.md (+ optional docs/md/*.md) -> project_report.tex -> project_report.pdf
# Mermaid blocks in README are rendered to PNG (pdflatex cannot draw them).
# Requirements: pandoc, pdflatex (BasicTeX / TinyTeX), mermaid-cli (mmdc) or npx
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"
export PATH="/Library/TeX/texbin:$PATH"

NAME="project_report"
BUILD_DIR="build"
README="../README.md"
TITLE="$(sed -n 's/^# *//p' "$README" | head -1 | sed 's/ *$//')"

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# 1. README -> build/README.md: drop the H1 (it becomes the document title)
#    and replace each ```mermaid block with a rendered image. A comment directly after the block,
#    <!-- Figure: Caption. {#fig-id} -->, becomes the figure caption and label.
awk -v dir="$BUILD_DIR" '
    function image(cap, id) { print "![" cap "](diagram" n ".png){" (id ? "#" id " " : "") "width=100%}" }
    !h1 && /^# / { h1 = 1; next }
    pending {
        pending = 0
        if (match($0, /^<!-- *Figure: *.* \{#[A-Za-z0-9_:-]+\} *-->$/)) {
            line = $0
            sub(/^<!-- *Figure: */, "", line); sub(/ *-->$/, "", line)
            id = line; sub(/.*\{#/, "", id); sub(/\}.*/, "", id)
            sub(/ *\{#.*/, "", line)
            image(line, id); next
        }
        image("", "")
    }
    /^```mermaid/ { n++; f = dir "/diagram" n ".mmd"; printf "" > f; inblk = 1; next }
    inblk && /^```/ { close(f); inblk = 0; pending = 1; next }
    inblk { print >> f; next }
    { print }
    END { if (pending) image("", "") }
' "$README" > "$BUILD_DIR/README.md"

for src in "$BUILD_DIR"/*.mmd; do
    [ -e "$src" ] || continue
    if command -v mmdc >/dev/null; then
        mmdc -q -i "$src" -o "${src%.mmd}.png" -b white -s 2
    elif command -v npx >/dev/null; then
        npx -y @mermaid-js/mermaid-cli -q -i "$src" -o "${src%.mmd}.png" -b white -s 2
    else
        echo "Cannot render $src: install mermaid-cli (npm i -g @mermaid-js/mermaid-cli)" >&2
        exit 1
    fi
done

# 2. Markdown -> LaTeX (extra chapters can be added as docs/md/*.md)
shopt -s nullglob
EXTRA=(md/*.md)
pandoc "$BUILD_DIR/README.md" ${EXTRA[@]+"${EXTRA[@]}"} -s -o "$NAME.tex" \
    -f markdown+lists_without_preceding_blankline \
    -M title="$TITLE" \
    -M author="Hanna Szczerbińska" \
    -M author="Zuzanna Zalewska" \
    -M date="$(LC_TIME=en_US.UTF-8 date '+%B %Y')" \
    --toc --toc-depth=2 \
    --number-sections --shift-heading-level-by=-1 \
    --lua-filter=filters/breakable-code.lua \
    --lua-filter=filters/tables.lua \
    --wrap=none \
    -V geometry:margin=1.5cm \
    -V colorlinks=true -V toccolor=black \
    --resource-path="$BUILD_DIR"

# Horizontal rule after every table body row (except the last one, which gets \bottomrule),
# table captions moved below the table, and a page break after the table of contents
awk '
    /\\tableofcontents/ { print; print "\\clearpage"; next }
    /^\\caption\{.*\\tabularnewline$/ { caption = $0; next }
    /\\endlastfoot/ { if (caption != "") { print caption; caption = "" } body = 1 }
    /\\end\{longtable\}/ { body = 0 }
    body && prev ~ / \\\\$/ && $0 !~ /\\end\{longtable\}/ { print "\\midrule\\noalign{}" }
    { print; prev = $0 }
' "$NAME.tex" > "$BUILD_DIR/$NAME.tex" && mv "$BUILD_DIR/$NAME.tex" "$NAME.tex"

# 3. LaTeX -> PDF (run twice so references are resolved; aux files go to build/)
for _ in 1 2; do
    TEXINPUTS="$BUILD_DIR:" pdflatex -interaction=nonstopmode -halt-on-error \
        -output-directory="$BUILD_DIR" "$NAME.tex" >/dev/null \
        || { echo "pdflatex failed, see docs/$BUILD_DIR/$NAME.log" >&2; exit 1; }
done
mv "$BUILD_DIR/$NAME.pdf" "$NAME.pdf"

echo "Done: docs/$NAME.tex, docs/$NAME.pdf"
