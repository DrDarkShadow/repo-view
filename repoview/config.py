"""All constants and classification rules for repoview."""

# ── Priorities ────────────────────────────────────────────────────────────────
PRIORITY_FOCUS               = 0   # focus mode — always full, never trimmed
PRIORITY_ESSENTIAL           = 1
PRIORITY_IMPORTANT_CODE      = 2
PRIORITY_SUPPORTING_CONFIG   = 3
PRIORITY_GENERAL_CODE        = 4
PRIORITY_GENERAL_TEXT        = 5
PRIORITY_METADATA_ONLY       = 10

# ── Essential filenames (always included at full content) ─────────────────────
ESSENTIAL_FILENAMES = {
    "requirements.txt", "pipfile", "pyproject.toml", "package.json",
    "composer.json", "gemfile", "dockerfile", "makefile", "readme.md",
    "readme", "contributing.md", "license.md", "license", "settings.py",
    "manage.py", "app.py", "main.py", "index.py", "server.py",
    "vite.config.js", "vite.config.ts", "webpack.config.js",
    "pom.xml", "build.gradle", "docker-compose.yml", "docker-compose.yaml",
    ".env.example", ".env.sample", "cargo.toml", "go.mod", "go.sum",
    "tsconfig.json", ".eslintrc.json", ".eslintrc.js", "jest.config.js",
    "jest.config.ts", "next.config.js", "next.config.ts",
}

# ── Code extensions ───────────────────────────────────────────────────────────
IMPORTANT_CODE_EXTS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".cs", ".go", ".rs",
    ".swift", ".kt", ".rb", ".php", ".c", ".cpp", ".h", ".hpp",
    ".html", ".css", ".scss", ".less", ".vue", ".svelte",
    ".sql", ".graphql", ".gql", ".proto", ".sol",
}

SUPPORTING_CONFIG_EXTS = {
    ".json", ".xml", ".yml", ".yaml", ".ini", ".conf",
    ".toml", ".cfg", ".sh", ".ps1", ".bat", ".tf", ".tfvars", ".env",
}

GENERAL_CODE_EXTS = {
    ".lua", ".pl", ".tcl", ".r", ".m", ".f", ".f90", ".ada",
    ".clj", ".ex", ".exs", ".erl", ".hs", ".dart", ".fs",
    ".fsx", ".gd", ".scala", ".tex",
}

# ── Metadata only (binary, never read) ───────────────────────────────────────
METADATA_ONLY_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".mp3", ".wav", ".ogg", ".mp4", ".mov", ".avi", ".webm",
    ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx",
    ".zip", ".tar", ".gz", ".rar", ".7z", ".jar",
    ".exe", ".dll", ".so", ".dylib", ".class", ".o",
    ".ttf", ".otf", ".woff", ".woff2", ".eot",
    ".lock", ".sum", ".DS_Store", ".pyc",
    ".log", ".cache", ".tmp", ".temp", ".bak",
}

# ── Doc extensions (skippable group 1) ───────────────────────────────────────
DOC_EXTS = {".md", ".txt", ".rst", ".mdx", ".markdown"}

# ── Test file patterns (skippable group 2) ───────────────────────────────────
TEST_FILENAME_PATTERNS = [
    r"^test_",          # test_foo.py
    r"_test\.",         # foo_test.go
    r"\.test\.",        # foo.test.js / foo.test.ts
    r"\.spec\.",        # foo.spec.ts / foo.spec.js
    r"^conftest\.",     # conftest.py
    r"^setup_tests\.",
]
TEST_DIR_NAMES = {"tests", "test", "__tests__", "spec", "specs", "e2e"}

# ── Always-excluded directories ───────────────────────────────────────────────
EXCLUDE_DIRS = {
    ".git", "node_modules", "vendor", "venv", "env", "envs",
    "__pycache__", "target", "build", "dist", "out", "bin", "obj",
    ".vscode", ".idea", ".gradle", ".pytest_cache", "coverage",
    "bower_components", ".mypy_cache", ".tox", ".nox", ".eggs",
    ".next", ".nuxt", ".svelte-kit", "storybook-static",
}

# ── Limits ────────────────────────────────────────────────────────────────────
MAX_FILE_SIZE_BYTES      = 50 * 1024 * 1024   # 50 MB
MAX_SIGNATURES_SUMMARY   = 20
MAX_LINES_FALLBACK       = 20
MAX_CHARS_TEXT_PREVIEW   = 3000
TOKEN_BUDGET             = 800_000

# ── Cache (stored in ~/.repoview/cache/) ──────────────────────────────────────
CACHE_DIR_NAME           = ".repoview"
CACHE_FILE_NAME          = "cache.json"
WATCH_DEBOUNCE_SECONDS   = 2.0