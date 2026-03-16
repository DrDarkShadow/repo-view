"""
Configuration and constants for codecontext.
"""

# --- Tokenizer ---
TIKTOKEN_ENCODING_NAME = "cl100k_base"

# --- Token Budget Presets ---
TOKEN_BUDGETS = {
    "Claude / GPT-4o (200k)": 200_000,
    "Claude 3.5 (800k)": 800_000,
    "GPT-4 Turbo (128k)": 128_000,
    "Gemini 1.5 Pro (1M)": 1_000_000,
    "Custom": None,
}
DEFAULT_TOKEN_BUDGET = 800_000

# --- Priority Levels ---
PRIORITY_ESSENTIAL = 1
PRIORITY_IMPORTANT_CODE = 2
PRIORITY_SUPPORTING_TEXT_CONFIG = 3
PRIORITY_GENERAL_CODE = 4
PRIORITY_GENERAL_TEXT = 5
PRIORITY_METADATA_ONLY = 10

# --- File Classification ---
ESSENTIAL_FILENAMES = {
    "requirements.txt", "pipfile", "pyproject.toml", "package.json",
    "composer.json", "gemfile", "dockerfile", "makefile", "readme.md",
    "readme", "contributing.md", "license.md", "license", "settings.py",
    "manage.py", "app.py", "main.py", "vite.config.js", "webpack.config.js",
    "pom.xml", "build.gradle", "docker-compose.yml", "docker-compose.yaml",
    ".env.example", ".env.sample",
}

IMPORTANT_CODE_EXTS = {
    ".py", ".js", ".ts", ".java", ".cs", ".go", ".rs", ".swift", ".kt",
    ".rb", ".php", ".c", ".cpp", ".h", ".hpp", ".html", ".css", ".scss",
    ".less", ".sql", ".graphql", ".gql", ".proto", ".sol", ".jsx", ".tsx",
    ".vue", ".svelte",
}

SUPPORTING_TEXT_CONFIG_EXTS = {
    ".md", ".txt", ".json", ".xml", ".yml", ".yaml", ".ini", ".conf",
    ".toml", ".cfg", ".sh", ".ps1", ".bat", ".tf", ".tfvars", ".env",
}

GENERAL_CODE_EXTS_FALLBACK = {
    ".S", ".asm", ".v", ".vhdl", ".lua", ".pl", ".tcl", ".r", ".m",
    ".f", ".f90", ".ada", ".clj", ".cljs", ".cljc", ".edn", ".ex",
    ".exs", ".erl", ".hrl", ".hs", ".lhs", ".dart", ".fs", ".fsx",
    ".fsi", ".gd", ".scala", ".sc", ".tex", ".cls", ".sty",
}

METADATA_ONLY_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".mp3", ".wav", ".ogg", ".mp4", ".mov", ".avi", ".webm",
    ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx",
    ".odt", ".ods", ".odp", ".zip", ".tar", ".gz", ".rar", ".7z",
    ".jar", ".war", ".ear", ".img", ".iso", ".bin", ".ttf", ".otf",
    ".woff", ".woff2", ".eot", ".exe", ".dll", ".so", ".dylib",
    ".class", ".o", ".a", ".lib", ".obj", ".pdb", ".DS_Store",
    ".bytes", ".lock", ".sum", ".swp", ".swo", ".bak", ".tmp",
    ".temp", ".bk", ".cache", ".log",
}

EXCLUDE_DIRS = {
    ".git", "node_modules", "vendor", "venv", "env", "envs",
    "__pycache__", "target", "build", "dist", "out", "bin", "obj",
    ".vscode", ".idea", ".project", ".settings", ".gradle",
    ".pytest_cache", "coverage", "site", "docs/_build",
    "bower_components", "jspm_packages", ".DS_Store",
    ".mypy_cache", ".tox", ".nox", ".eggs",
}

# --- Summary Settings ---
MAX_FILE_SIZE_TO_READ_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_SIGNATURES_CODE_SUMMARY = 20
MAX_LINES_CODE_SUMMARY_FALLBACK = 20
MAX_CHARS_TEXT_SUMMARY = 3000

# --- Category Labels (for interactive UI) ---
CATEGORY_LABELS = {
    "essential": "Essential files (README, requirements, Dockerfile…)",
    "code": "Source code (.py, .js, .ts, .go, .rs…)",
    "config": "Config & text files (.json, .yml, .md, .toml…)",
    "general_code": "Rare languages (.lua, .dart, .scala, .hs…)",
    "general_text": "Other text files (unclassified extensions)",
}twine upload dist/*                    # PyPI pe upload
