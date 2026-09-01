import re


INTENT_SIGNAL_PATTERNS = [
    ("looking_for", 3, r"\blooking\s+for\b"),
    ("looking_to_hire", 4, r"\blooking\s+to\s+hire\b"),
    ("need_person", 3, r"\bneed(?:s|ed|ing)?\s+(?:someone|somebody|a|an|freelancer|developer|designer|programmer)\b"),
    ("need_help", 2, r"\bneed(?:s|ed|ing)?\s+help\b"),
    ("need_to_work", 2, r"\b(?:i|we)\s+need\s+to\s+(?:build|create|develop|make|design|fix|repair|debug|solve|automate|integrate|deploy|set\s+up|setup)\b"),
    ("hiring", 4, r"\b(?:hiring|hire|want(?:ing)?\s+to\s+hire)\b"),
    ("can_anyone_help", 3, r"\bcan\s+anyone\s+(?:help|recommend)\b"),
    ("anyone_know_someone", 3, r"\banyone\s+(?:know|knows)\s+(?:someone|somebody|anyone)\b"),
    ("who_can", 3, r"\b(?:who|someone|somebody)\s+can\b"),
    ("searching_for", 3, r"\b(?:searching\s+for|seeking)\b"),
    ("role_needed", 4, r"\b(?:freelancer|developer|designer|programmer|virtual\s+assistant|va)\s+needed\b"),
]

SERVICE_SIGNAL_PATTERNS = [
    ("developer", 2, r"\bdeveloper\b"),
    ("programmer", 2, r"\bprogrammer\b"),
    ("python", 2, r"\bpython\b"),
    ("django", 2, r"\bdjango\b"),
    ("web_developer", 2, r"\bweb\s+developer\b"),
    ("software_developer", 2, r"\bsoftware\s+developer\b"),
    ("website", 2, r"\bweb\s*site\b|\bwebsite\b"),
    ("web_application", 2, r"\bweb\s+(?:app|application)\b"),
    ("mobile_app", 2, r"\bmobile\s+app\b"),
    ("app", 1, r"\bapp(?:lication)?\b"),
    ("designer", 2, r"\bdesigner\b"),
    ("graphic_designer", 2, r"\bgraphic\s+designer\b"),
    ("ui_ux", 2, r"\bui\b|\bux\b|\bui\s*/\s*ux\b"),
    ("wordpress", 2, r"\bword\s*press\b|\bwordpress\b"),
    ("ecommerce", 2, r"\be-?commerce\b"),
    ("automation", 2, r"\bautomation\b|\bautomate\b"),
    ("bot", 2, r"\bbot\b"),
    ("api", 2, r"\bapi\b"),
    ("database", 2, r"\bdatabase\b"),
    ("excel", 2, r"\bexcel\b|\bspreadsheet\b|\bgoogle\s+sheets?\b"),
    ("data_science", 2, r"\bdata\s+science\b"),
    ("machine_learning", 2, r"\bmachine\s+learning\b|\bml\b"),
    ("ai", 2, r"\bai\b"),
    ("seo", 2, r"\bseo\b"),
    ("marketing", 2, r"\bmarketing\b"),
    ("content", 1, r"\bcontent\b"),
    ("video_editing", 2, r"\bvideo\s+edit(?:ing|or)?\b"),
    ("virtual_assistant", 2, r"\bvirtual\s+assistant\b|\bva\b"),
    ("freelancer", 2, r"\bfreelanc(?:e|er|ing)\b"),
]

PROBLEM_SIGNAL_PATTERNS = [
    ("build", 2, r"\b(?:build|create|develop|make|design)\b"),
    ("fix", 2, r"\b(?:fix|repair|debug|solve)\b"),
    ("automate", 2, r"\bautomat(?:e|ing|ion)\b"),
    ("integrate", 1, r"\b(?:integrate|integration|api\s+integration)\b"),
    ("deploy", 1, r"\b(?:deploy|deployment|setup|set\s+up)\b"),
    ("broken", 2, r"\b(?:broken|not\s+working|isn'?t\s+working|crash(?:ing|es|ed)?|keeps\s+crashing)\b"),
    ("error", 1, r"\b(?:error|bug|issue|problem|failed|failure)\b"),
    ("not_responsive", 1, r"\bnot\s+responsive\b|\bisn'?t\s+responsive\b"),
    ("cant_figure_out", 1, r"\b(?:can'?t|cannot)\s+figure\s+out\b"),
]

COMMERCIAL_SIGNAL_PATTERNS = [
    ("paid", 1, r"\bpaid\b|\bpaid\s+project\b"),
    ("budget", 1, r"\bbudget\b"),
    ("payment", 1, r"\bpayment\b|\bpaying\b"),
    ("client", 1, r"\bclient\b"),
    ("project", 1, r"\bproject\b"),
    ("contract", 1, r"\bcontract\b"),
    ("proposal", 1, r"\bproposal\b"),
    ("quote", 1, r"\bquote\b"),
    ("price", 1, r"\bprice\b"),
    ("rate", 1, r"\brate\b"),
    ("compensation", 1, r"\bcompensation\b"),
    ("salary", 1, r"\bsalary\b"),
    ("freelance", 1, r"\bfreelance\b"),
]

URGENCY_SIGNAL_PATTERNS = [
    ("urgent", 1, r"\burgent\b"),
    ("asap", 1, r"\basap\b"),
    ("today", 1, r"\btoday\b"),
    ("immediately", 1, r"\bimmediately\b"),
    ("as_soon_as_possible", 1, r"\bas\s+soon\s+as\s+possible\b"),
    ("this_week", 1, r"\bthis\s+week\b"),
    ("deadline", 1, r"\bdeadline\b"),
    ("quickly", 1, r"\bquickly\b"),
]

NEGATIVE_SIGNAL_PATTERNS = [
    ("self_promotion", 3, r"\b(?:i\s+am|i'm|im|we\s+are|we're)\s+(?:a|an)?\s*(?:python\s+|django\s+|web\s+|software\s+)?(?:developer|designer|programmer|freelancer|agency)\b"),
    ("as_a_provider", 3, r"\bas\s+(?:a|an)\s+(?:developer|designer|programmer|freelancer)\b"),
    ("developer_here", 3, r"\b(?:developer|designer|programmer)\s+here\b"),
    ("work_as_provider", 3, r"\bi\s+work\s+as\s+(?:a|an)\s+(?:developer|designer|programmer|freelancer)\b"),
    ("you_need_context", 2, r"\byou\s+need\b|\bu\s+need\b"),
    ("your_need_context", 2, r"\byour\s+need\b|\baccording\s+to\s+your\s+need\b"),
    ("needed_for_context", 2, r"\bneeded\s+for\b|\bno\s+\w+\s+needed\b"),
    ("your_website_context", 2, r"\byour\s+(?:web\s*site|website|app)\s+(?:is|was|not|isn'?t)\b"),
    ("sales_question", 2, r"\b(?:do\s+you\s+want|if\s+you\s+want|what\s+you\s+want|you\s+want\s+to)\b"),
    ("tutorial_context", 3, r"\b(?:tutorial|documentation|example|code\s+explanation|how\s+to|why\s+does|why\s+is)\b"),
    ("available_provider", 2, r"\b(?:available\s+for|dm\s+me|inbox\s+me|contact\s+me)\b"),
]

INTERESTED_SIGNAL_PATTERNS = [
    ("interested", 0, r"\binterested\b"),
]

COMPILED_INTENT_SIGNAL_PATTERNS = [
    (name, weight, re.compile(pattern, re.IGNORECASE))
    for name, weight, pattern in INTENT_SIGNAL_PATTERNS
]
COMPILED_SERVICE_SIGNAL_PATTERNS = [
    (name, weight, re.compile(pattern, re.IGNORECASE))
    for name, weight, pattern in SERVICE_SIGNAL_PATTERNS
]
COMPILED_PROBLEM_SIGNAL_PATTERNS = [
    (name, weight, re.compile(pattern, re.IGNORECASE))
    for name, weight, pattern in PROBLEM_SIGNAL_PATTERNS
]
COMPILED_COMMERCIAL_SIGNAL_PATTERNS = [
    (name, weight, re.compile(pattern, re.IGNORECASE))
    for name, weight, pattern in COMMERCIAL_SIGNAL_PATTERNS
]
COMPILED_URGENCY_SIGNAL_PATTERNS = [
    (name, weight, re.compile(pattern, re.IGNORECASE))
    for name, weight, pattern in URGENCY_SIGNAL_PATTERNS
]
COMPILED_NEGATIVE_SIGNAL_PATTERNS = [
    (name, weight, re.compile(pattern, re.IGNORECASE))
    for name, weight, pattern in NEGATIVE_SIGNAL_PATTERNS
]
COMPILED_INTERESTED_SIGNAL_PATTERNS = [
    (name, weight, re.compile(pattern, re.IGNORECASE))
    for name, weight, pattern in INTERESTED_SIGNAL_PATTERNS
]


def find_weighted_signals(text, compiled_patterns):
    signals = []

    for name, weight, compiled_pattern in compiled_patterns:
        if compiled_pattern.search(text):
            signals.append({"name": name, "weight": weight})

    return signals


def find_intent_signals(text):
    return find_weighted_signals(text, COMPILED_INTENT_SIGNAL_PATTERNS)


def find_service_signals(text):
    return find_weighted_signals(text, COMPILED_SERVICE_SIGNAL_PATTERNS)


def find_problem_signals(text):
    return find_weighted_signals(text, COMPILED_PROBLEM_SIGNAL_PATTERNS)


def find_commercial_signals(text):
    return find_weighted_signals(text, COMPILED_COMMERCIAL_SIGNAL_PATTERNS)


def find_urgency_signals(text):
    return find_weighted_signals(text, COMPILED_URGENCY_SIGNAL_PATTERNS)


def find_negative_signals(text):
    return find_weighted_signals(text, COMPILED_NEGATIVE_SIGNAL_PATTERNS)


def find_interested_signals(text):
    return find_weighted_signals(text, COMPILED_INTERESTED_SIGNAL_PATTERNS)
