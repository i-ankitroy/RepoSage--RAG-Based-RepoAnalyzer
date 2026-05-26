from setuptools import setup, find_packages

setup(
    name="reposage",
    version="1.0.0",
    packages=find_packages(include=["backend", "backend.*"]),
    install_requires=[
        "fastapi>=0.100.0",
        "uvicorn[standard]>=0.22.0",
        "pydantic>=2.0.0",
        "chromadb>=0.4.0",
        "sentence-transformers>=2.2.2",
        "typer>=0.9.0",
        "python-dotenv>=1.0.0",
        "httpx>=0.24.0",
        "gitpython>=3.1.30",
        "python-multipart>=0.0.6"
    ],
    entry_points={
        "console_scripts": [
            "reposage=backend.cli:cli_app",
        ],
    },
    python_requires=">=3.11",
)
