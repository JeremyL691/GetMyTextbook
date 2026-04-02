from pathlib import Path

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
CACHE_DIR = BASE_DIR / ".cache"
HTML_CACHE_DIR = CACHE_DIR / "html"
IMAGE_CACHE_DIR = CACHE_DIR / "images"

DEFAULT_TIMEOUT = 20
DEFAULT_REQUEST_DELAY = 0.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_HTML_WORKERS = 8
DEFAULT_IMAGE_WORKERS = 12

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

IMAGE_PROFILES = {
    "fast": {
        "max_width": 300,
        "jpeg_quality": 28,
        "skip_small_images": True,
        "min_dimension": 96,
    },
    "balanced": {
        "max_width": 520,
        "jpeg_quality": 48,
        "skip_small_images": True,
        "min_dimension": 72,
    },
    "high": {
        "max_width": 960,
        "jpeg_quality": 74,
        "skip_small_images": False,
        "min_dimension": 0,
    },
}

DEFAULT_IMAGE_PROFILE = "fast"

SITES = {
    "ds100": {
        "label": "DS100 Course Notes",
        "base_url": "https://ds100.org/course-notes/",
        "subtitle": "Principles and Techniques of Data Science",
    },
    "cs61b": {
        "label": "CS61B Textbook",
        "base_url": "https://cs61b-2.gitbook.io/cs61b-textbook",
        "subtitle": "GitBook Export",
    },
}

DS100_TOC_SNAPSHOT = [
    ("Welcome", "https://ds100.org/course-notes/"),
    ("Introduction", "https://ds100.org/course-notes/introduction"),
    ("Pandas I", "https://ds100.org/course-notes/pandas-1"),
    ("Pandas II", "https://ds100.org/course-notes/pandas-2"),
    ("Pandas III", "https://ds100.org/course-notes/pandas-3"),
    ("Data Cleaning and EDA", "https://ds100.org/course-notes/eda"),
    ("Regular Expressions", "https://ds100.org/course-notes/regex"),
    ("Visualization I", "https://ds100.org/course-notes/visualization-1"),
    ("Visualization II", "https://ds100.org/course-notes/visualization-2"),
    ("Sampling", "https://ds100.org/course-notes/sampling"),
    ("Modeling & SLR", "https://ds100.org/course-notes/modeling-slr"),
    ("Constant Model, Loss, and Transformations", "https://ds100.org/course-notes/loss-transformations"),
    ("Ordinary Least Squares", "https://ds100.org/course-notes/ols"),
    ("sklearn and Gradient Descent", "https://ds100.org/course-notes/gradient-descent"),
    ("Gradient Descent Continuation, Feature Engineering", "https://ds100.org/course-notes/feature-engineering"),
    ("Cross Validation and Regularization", "https://ds100.org/course-notes/cv-reg"),
    ("Case Study in Human Contexts and Ethics", "https://ds100.org/course-notes/case-study-hce"),
    ("Random Variables", "https://ds100.org/course-notes/probability-1"),
    ("Estimators, Bias, and Variance", "https://ds100.org/course-notes/probability-2"),
    ("Parameter Inference and Bootstrapping (Fall 2025)", "https://ds100.org/course-notes/inference-causality"),
    ("SQL I (Fall 2025)", "https://ds100.org/course-notes/sql-i"),
    ("SQL II (Fall 2025)", "https://ds100.org/course-notes/sql-ii"),
    ("Logistic Regression I (Fall 2025)", "https://ds100.org/course-notes/logistic-reg-1"),
    ("Logistic Regression II (Fall 2025)", "https://ds100.org/course-notes/logistic-reg-2"),
    ("Clustering (Fall 2025)", "https://ds100.org/course-notes/clustering"),
    ("PCA (Fall 2025)", "https://ds100.org/course-notes/pca"),
]
