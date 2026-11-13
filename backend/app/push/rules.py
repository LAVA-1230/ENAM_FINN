"""Keyword -> category rules (spec Appendix 17.1), tuned on live NSE data (Oct-Nov 2026).

Each rule matches NSE's own category text (`desc`) and/or the subject. First match wins.
Order matters: specific red flags first, routine paperwork before the broad patterns."""
import re

CATEGORIES = ["auditor_change", "default", "kmp_change", "results", "rating", "pledge_sast", "insider",
              "mna", "fundraise", "buyback", "order_win", "capex", "litigation", "clarification",
              "concall_doc", "dividend_corp", "board_meeting", "routine", "other"]

# (category, pattern on desc, pattern on subject). Either may be None.
RULES: list[tuple[str, str | None, str | None]] = [
    # paperwork that mentions scary words but isn't: internal/secretarial/cost auditors, RTA changes
    ("routine", None, r"(internal|secretarial|cost|joint internal) auditors?"),
    ("routine", r"^(trading window|copy of newspaper publication|certificate under sebi|esop|esos|esps|"
                r"loss of share certificate|duplicate share|updates? - rta|shareholding pattern|"
                r"compliance certificate|statement of investor complaints|closure of trading window)",
     r"trading window|newspaper (publication|advertisement)|duplicate share certificate|loss of share certificate|"
     r"74\(5\)|esop allotment|allotment under esop|compliance certificate|shareholding pattern|"
     r"investor education and protection fund|iepf|registrar (and|&) share transfer|\brta\b|"
     r"regulation 74|depositories and participants|change of address"),
    ("auditor_change", r"^(change in auditors|resignation of auditor)",
     r"resignation of (the )?(statutory )?auditor|statutory auditors?.*(resign|appoint|change)|auditor.*resign"),
    ("default", r"default|delay in (payment|servicing)",
     r"\bdefault\b|delay in (payment|servicing)|non-payment of (interest|principal)"),
    # these mention "financial results" but are not the results filing itself
    ("board_meeting", r"^board meeting intimation", r"board meeting (intimation|to be held|is scheduled)|meeting of the board .* is scheduled"),
    ("concall_doc", r"^(press release|investor presentation|analysts?/institutional investor meet)", None),
    ("results", r"^(financial results?|integrated filing.*financial)",
     r"financial results?|integrated filing.*financial|(un)?audited.*results"),
    ("kmp_change", r"^(resignation|cessation|appointment|retirement|change in (director|management|key managerial|"
                   r"company secretary|kmp)|resignation of director)",
     r"\b(resignation|cessation|retirement)\b.*\b(director|officer|ceo|cfo|chairman|secretary|kmp|smp|md)\b|"
     r"appointment of .*(chief|cfo|ceo|managing director|company secretary|compliance officer|whole[- ]?time director|director|chairman)|"
     r"change in (directors|key managerial personnel|kmp|management)"),
    ("rating", r"credit rating", r"credit rating|rating (action|reaffirm|upgrade|downgrade)|\b(crisil|icra|care ?edge|india ratings|fitch|moody)"),
    ("pledge_sast", r"pledge|encumbrance|sast|takeover", r"pledge|encumbrance|regulation 31|\bsast\b|takeover regulations"),
    ("insider", r"insider trading|regulation 7", r"regulation 7\s*\(2\)|insider trading|pit regulations"),
    ("buyback", r"buy ?back", r"buy[- ]?back"),
    ("mna", r"^(acquisition|amalgamation|merger|demerger|scheme of arrangement|sale or disposal|"
            r"restructuring|joint venture)",
     r"\bacquisition\b|amalgamation|\bmerger\b|demerger|scheme of arrangement|divest|sale of (stake|undertaking)|"
     r"disposal|joint venture|wholly owned subsidiary.*(incorporat|acquir)"),
    ("fundraise", r"^(issue of securities|qip|preferential|rights issue|allotment of securities|"
                  r"non-convertible|commercial paper)",
     r"\bqip\b|qualified institutions placement|rights issue|preferential (issue|allotment)|\bwarrants\b|"
     r"non-convertible debentures|\bncds?\b|issue of (equity|debentures|bonds)"),
    ("order_win", r"bagging|receiving of orders|award of order", r"order (win|received|bagged|inflow)|bags (an )?orders?|letter of award|contract (award|win)|bagging"),
    ("capex", r"capacity|commencement of (commercial )?(production|operations)",
     r"capacity expansion|\bcapex\b|commissioning|new plant|greenfield|brownfield|commencement of commercial production"),
    ("litigation", r"litigation|action\(s\) taken|orders passed|regulatory action",
     r"litigation|show cause|penalty|tax demand|warning letter|order (from|of|by) .*(sebi|rbi|court|tribunal|gst|income tax)"),
    ("clarification", r"clarification|rumour verification", r"clarification|spurt in (price|volume)|price movement|rumou?r"),
    ("concall_doc", r"analysts?/institutional investor meet|investor presentation|press release|con\. call",
     r"transcript|analyst.*(meet|call)|investor (meet|presentation)|earnings call|con\.? ?call|press release"),
    ("dividend_corp", r"^(dividend|bonus|record date|stock split|sub-division|book closure)",
     r"\bdividend\b|\bbonus\b|\bsplit\b|sub-division|record date"),
    ("board_meeting", r"^board meeting intimation", r"board meeting (intimation|to be held)|prior intimation"),
    # outcome-of-board-meeting without results is mostly paperwork
    ("routine", r"^(outcome of board meeting|shareholders meeting|"
                r"options to purchase securities|giving guarantees)", None),
]

# NSE's catch-all categories. Unmatched filings with these go to the LLM; if no LLM, they are routine.
GENERIC_DESC_RE = re.compile(r"^(general updates|updates|other|disclosure under sebi)", re.I)

_COMPILED = [(c, re.compile(d, re.I) if d else None, re.compile(s, re.I) if s else None) for c, d, s in RULES]

# Concall-doc sub-type: which of these are the transcript (feeds docs refresh) vs scheduling noise.
SCHEDULE_RE = re.compile(r"schedule of|intimation of (the )?schedule|link of (the )?recording|audio recording|"
                         r"participation in|conclusion of", re.I)


def classify(desc: str, subject: str) -> str | None:
    d, s = (desc or "").strip(), (subject or "").strip()
    for cat, dp, sp in _COMPILED:
        if (dp and dp.search(d)) or (sp and sp.search(s)):
            if cat == "results" and re.search(r"newspaper", s, re.I):
                return "routine"
            return cat
    return None


def is_schedule_noise(subject: str) -> bool:
    return bool(SCHEDULE_RE.search(subject or ""))
