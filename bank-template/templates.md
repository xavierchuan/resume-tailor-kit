---
templates:
  quant: quant.tex
  ai: ai.tex
  software: software.tex
routing_defaults:
  fallback: software.tex
routing_rules:
  - "quant -> quant"
  - "ai -> ai"
  - "data|software -> software"
---

# Template Routing

Edit the frontmatter if your local LaTeX template names differ.

