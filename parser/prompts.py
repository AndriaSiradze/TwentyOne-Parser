from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate

from parser.parsing_models import NewsParsingModel, NewsParsingModelRu, SimilarityCheckResult, RelevanceCheck

# --- DEDUP: stricter JSON-only, clearer criteria ---

CHECK_DUPLICATES = """
Task: Decide if the new title is about the same news event as any of the existing titles.

Input
title_to_check: {title}
existing_titles: {all_titles}

Same event if:
1) The same announcement/action by the same person(s) or organization(s).
2) The same development/update, even if phrased differently.

Output
Return ONLY valid JSON per schema. No prose, no explanations, no extra keys, no markdown.

{format_instructions}
"""

# --- EN SUMMARY: sectionless JSON fields, no bullets, snappier caps, strict guards ---

SUMMARIZE_AND_FORMAT_TEMPLATE = """
Read the article and produce a concise English brief for Bitcoin readers.

Article
```
{context}
```

Output
Return ONLY valid JSON per schema. No markdown, no bullets, no section labels, no emojis, no extra keys.
Populate the schema fields exactly as required by {format_instructions}. Apply the following rules to each field:

Title
- Wrap in <b>...</b>.
- 7–10 words. Active verb. No colon, no dash, no filler.

Overview
- Wrap in <i>...</i>.
- Exactly 1 sentence, ≤16 words, ≤1 comma.
- State the action + why Bitcoin readers care.

Explanation
- 1–2 sentences, ≤60 words total.
- Don’t repeat title or overview wording.
- Structure: What happened (+numbers/specifics) → Mechanism/impact for Bitcoin’s market/tech/community.

Quote
- Include only if present and impactful.
- Must be wrapped in quotation marks: "<i>Quote</i>" — Attribution.
- ≤20 words inside the quote. Capitalize the first letter.
- If no suitable quote, use an empty string.

Tags
- 0–2 items only from this whitelist (exact forms): #lightning #mining #economy #protocol #releases #privacy #regulation #security #investment #scam #speculation
- Never place hashtags in any other field.

Line breaks and spacing (strict)
- Insert exactly one empty line between each section:
title:
  - Title
body:
  -  Overview → Explanation
  - After Explanation → Quote (if present)
  - After Quote
tags:
  - Tags → Source (if present)
- Do not insert extra blank lines inside any field.
- Do not omit any required blank lines.

Formatting rules
- Allowed HTML tags only: <b>, <strong>, <i>, <em>, <u>, <ins>, <s>, <strike>, <del>, <a href="...">, <code>, <pre>, <span class="tg-spoiler">, <tg-spoiler>, <blockquote>
- No leading dashes or bullets in any field.
- Do not include section names (e.g., “Overview”, “Explanation”) in any field.
- Each field stands alone; do not concatenate multiple sections into one field.
- Use standard spaces and punctuation.

Style
- Brisk, neutral newsroom tone. Concrete verbs and nouns. No hype, no opinions.
- Avoid abstract fillers (“strengthened signals”, “consolidated accumulation”).
- Use digits with short scales (K/M/B), signed percents, and dates in “Mon DD, YYYY”.

Validation checklist (must-pass)
- JSON only, matches schema from {format_instructions}.YOU MUST FOLLOW THIS SCHEMA ONLY 3 
title:
    - Title 7–10 words in <b>...</b>.
body:
    - Overview exactly 1 sentence in <i>...</i>, ≤16 words, ≤1 comma.
    - Explanation ≤2 sentences, ≤60 words.
    - Quote (if present) is wrapped in quotation marks and <i>...</i>.
tags:
- Exactly 0–2 tags from whitelist; none elsewhere.
- Required line breaks between all sections.
"""

# --- RU TRANSLATION: tighter style, 1:1 tags, quote attribution rules ---

TRANSLATION_TEMPLATE = """
Translate the English summary into Russian. Preserve structure and HTML tags exactly.

Source

```
{context}
```

Output
Return ONLY valid JSON per schema. No markdown, no bullets, no extra keys. Preserve field order and tags.

Style and length
- Keep sentences short; remove filler. Neutral, brisk tone.
- <b>Title</b> — ≤65 characters, active verb, no colon.
- <i>Overview</i> — exactly 1 sentence.
- Explanation — 1 paragraph or 2 short paragraphs, 60–90 words total, no repetition.
- "<i>Quote</i>" — must be wrapped in quotation marks. Translate quote text; preserve attribution per rules below.
- Hashtags — 0–2 from the Russian whitelist, matching English tags 1:1. If English has 0, Russian has 0.

Hashtag whitelist (Russian, exact forms)
#лайтнинг #майнинг #экономика #протокол #релизы #приватность #регуляции #безопасность #инвестиции #скам #спекуляции

Quote attribution rules
- Real person’s name: transliterate name to Russian; translate role/title; keep company names and BTC in original.
- Nickname/pseudonym/handle (e.g., contains “@”, no spaces, stylized alias): do NOT translate or transliterate the handle; keep as is.
- Platform mentions (e.g., “on X”, “in Telegram”): translate the preposition; keep platform name standard in Russian UI contexts.
- Company names and BTC: do not translate.

Natural Russian (no calques or coinages)
- Do NOT invent adjectives or direct calques from English (e.g., avoid forms like “спросовой”). Prefer noun phrases: “поддержка спроса”, “рост спроса”.
- Prefer standard market terms: “уровень поддержки/сопротивления”, “откат”, “волатильность”, “притоки/оттоки”, “капитализация”, “доминирование”, “ликвидность”, “спотовый рынок”, “фьючерсы”, “открытый интерес”, “базис”.
- Allowed community jargon when natural: “ралли”, “сетап”, “медвежий/бычий” — use sparingly; default to neutral equivalents where clearer.

Numbers and dates (Russian conventions)
- Dates: "DD месяц YYYY" (e.g., "11 августа 2020").
- Prices: "X XXX долларов".
- Percents: "+X,X%" or "-X,X%".
- Do NOT translate company names or BTC.

Line breaks and spacing (strict)
- Insert exactly one empty line between each section:
  - After Title → Overview
  - After Overview → Explanation
  - After Explanation → Quote (if present)
  - After Quote → Tags (if present)
  - After Tags → Source (if present)
- Do not insert extra blank lines inside any field.
- Do not omit any required blank lines.

Formatting rules
- Allowed HTML tags only: <b>, <strong>, <i>, <em>, <u>, <ins>, <s>, <strike>, <del>, <a href="...">, <code>, <pre>, <span class="tg-spoiler">, <tg-spoiler>, <blockquote>
- No hashtags in any field except the tags array.
- Each field stands alone; do not merge sections into one field.

Terminology
{terms}

Validation checklist (must-pass)
- JSON only, matches schema from {format_instructions}.YOU MUST FOLLOW THIS SCHEMA ONLY 3 
title_ru:
    - Title 7–10 words in <b>...</b>.
body_ru:
    - Overview if there is some
    - Explanation body
    - Quote if there is some 
tags_ru:
- Exactly 0–2 tags from whitelist; none elsewhere.
- Required line breaks between all sections.
"""

RELEVANCE_CHECK = """

```
```
You are a Bitcoin‑only news relevance classifier.


{context}


Decision criteria (inclusive):

1. Approve if the article is primarily and substantively about Bitcoin.
   • Reject if Bitcoin is only mentioned briefly or as part of a generic crypto market list.
   • Reject if the majority of the article is about other blockchains, tokens, or projects.

2. Approve if about regulation of crypto assets overall or Bitcoin specifically.
   • Reject if regulation is only about specific altcoins or does not directly apply to Bitcoin.

3. Approve if about court cases, legal actions, imprisonments, or investigations involving individuals or entities working in the Bitcoin field.
   • Include people in privacy tools, freedom tech, or human rights work.
   • Reject if legal matter is only related to altcoin projects.

4. Approve if about major scams, even if they involve altcoins or general finance, **only if Bitcoin is directly involved**.

5. Approve if about significant computational infrastructure (e.g., data centers, mining regulation, supercomputers, quantum computing) **and** the infrastructure is used for or directly impacts Bitcoin.
   • Reject if infrastructure is only for altcoins.

6. Approve if about macro‑economic, financial, exchange, or corporate events with a **clear, direct, and explicit** Bitcoin impact.
   • Reject if Bitcoin is mentioned only as one of several assets affected.
   • Examples for approval: Bitcoin ETFs, corporate treasury moves involving Bitcoin, BTC‑specific exchange actions, monetary policy explicitly tied to Bitcoin.

7. Approve if about Bitcoin technical, geopolitical, or energy‑policy developments directly affecting the Bitcoin network.
   • Examples: BIPs, Lightning upgrades, Taproot adoption, mining bans, subsidies, sanctions on BTC transactions.

{format_instructions}

Rules:
• Err on the side of marking borderline or tangential cases as NOT relevant.
• Never approve solely because Bitcoin is mentioned; require direct and substantial connection.
• If multiple criteria apply, pick the strongest one and explain briefly in 'reason'.
• Never include extra keys, commentary, or text outside the JSON.

"""

llm_relevance_parser = JsonOutputParser(pydantic_object=RelevanceCheck)
llm_duplicates_parser = JsonOutputParser(pydantic_object=SimilarityCheckResult)
llm_output_parser = JsonOutputParser(pydantic_object=NewsParsingModel)
llm_ru_output_parser = JsonOutputParser(pydantic_object=NewsParsingModelRu)

RELEVANCE_CHECK_PROMPT = PromptTemplate(
    template=RELEVANCE_CHECK,
    input_variables=['context'],
    partial_variables={'format_instructions': llm_relevance_parser.get_format_instructions()}
)
DUPLICATES_CHECK_PROMPT = PromptTemplate(
    template=CHECK_DUPLICATES,
    input_variables=["title", 'all_titles'],
    partial_variables={'format_instructions': llm_duplicates_parser.get_format_instructions()}
)

TRANSLATE_PROMPT = PromptTemplate(
    template=TRANSLATION_TEMPLATE,
    input_variables=["context", 'terms'],
    partial_variables={'format_instructions': llm_ru_output_parser.get_format_instructions()}
)
SUMMARIZE_PROMPT = PromptTemplate(
    template=SUMMARIZE_AND_FORMAT_TEMPLATE,
    input_variables=["context"],
    partial_variables={'format_instructions': llm_output_parser.get_format_instructions()}
)
