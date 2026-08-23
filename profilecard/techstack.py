"""Work out what someone actually builds with, from what their repos contain.

GitHub's language statistics measure *bytes of source*, which answers a
different question than the one you want on a profile card.  One large legacy
service can outweigh every recent project put together, and the languages API
has no notion of when anything was written.  It also cannot see a framework, a
cloud, or a database -- Next.js, Vercel and Postgres are all just "TypeScript".

So this reads dependency manifests and marker files instead, and reports each
technology by *how many repositories use it*.  Breadth of use is a better signal
than volume of text, and it is immune to one enormous repository skewing
everything.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

# Dependency name -> label.  A trailing "/" matches a scope prefix
# (``@aws-sdk/`` catches every client package); anything else is an exact match.
DEPENDENCY_SIGNALS: dict[str, str] = {
    # Frameworks and UI
    "next": "Next.js",
    "react": "React",
    "react-native": "React Native",
    "expo": "Expo",
    "vue": "Vue",
    "svelte": "Svelte",
    "@angular/": "Angular",
    "@remix-run/": "Remix",
    "astro": "Astro",
    "tailwindcss": "Tailwind",
    "@radix-ui/": "Radix UI",
    "@shadcn/ui": "shadcn/ui",
    # Runtime and server
    "express": "Express",
    "fastify": "Fastify",
    "@nestjs/": "NestJS",
    "hono": "Hono",
    "socket.io": "WebSockets",
    "ws": "WebSockets",
    # Data
    "pg": "Postgres",
    "postgres": "Postgres",
    "@neondatabase/serverless": "Postgres",
    "drizzle-orm": "Drizzle",
    "prisma": "Prisma",
    "@prisma/client": "Prisma",
    "knex": "SQL",
    "mongoose": "MongoDB",
    "mongodb": "MongoDB",
    "redis": "Redis",
    "ioredis": "Redis",
    "@upstash/redis": "Redis",
    "@supabase/": "Supabase",
    "firebase": "Firebase",
    "firebase-admin": "Firebase",
    # Cloud
    "@aws-sdk/": "AWS",
    "aws-sdk": "AWS",
    "aws-cdk-lib": "AWS CDK",
    "@google-cloud/": "GCP",
    "@vercel/": "Vercel",
    "@flags-sdk/vercel": "Vercel",
    "@azure/": "Azure",
    # AI
    "@anthropic-ai/sdk": "Claude API",
    "openai": "OpenAI",
    "ai": "AI SDK",
    "langchain": "LangChain",
    # Payments and services
    "stripe": "Stripe",
    "@stripe/stripe-js": "Stripe",
    "twilio": "Twilio",
    "resend": "Resend",
    "@sendgrid/mail": "SendGrid",
    # Tooling
    "typescript": "TypeScript",
    "vitest": "Vitest",
    "jest": "Jest",
    "playwright": "Playwright",
    "@playwright/test": "Playwright",
    "cypress": "Cypress",
    "turbo": "Turborepo",
}

# Files or directories in the repository root -> label.
FILE_SIGNALS: dict[str, str] = {
    "vercel.json": "Vercel",
    ".vercelignore": "Vercel",
    "next.config.js": "Next.js",
    "next.config.ts": "Next.js",
    "next.config.mjs": "Next.js",
    "dockerfile": "Docker",
    "docker-compose.yml": "Docker",
    "docker-compose.yaml": "Docker",
    "app.yaml": "GCP",
    "cloudbuild.yaml": "GCP",
    "serverless.yml": "Serverless",
    "template.yaml": "AWS SAM",
    "main.tf": "Terraform",
    "terraform": "Terraform",
    "supabase": "Supabase",
    "prisma": "Prisma",
    "drizzle.config.ts": "Drizzle",
    "go.mod": "Go",
    "cargo.toml": "Rust",
    "requirements.txt": "Python",
    "pyproject.toml": "Python",
    "gemfile": "Ruby",
    "pubspec.yaml": "Flutter",
}


@dataclass
class Technology:
    name: str
    repos: int  # how many repositories it appears in


def _match_dependency(name: str) -> str | None:
    if name in DEPENDENCY_SIGNALS:
        return DEPENDENCY_SIGNALS[name]
    for pattern, label in DEPENDENCY_SIGNALS.items():
        if pattern.endswith("/") and name.startswith(pattern):
            return label
    return None


def signals_for_repo(package_json: str | None, root_entries: list[str]) -> set[str]:
    """Every technology a single repository shows evidence of."""
    found: set[str] = set()

    if package_json:
        try:
            pkg = json.loads(package_json)
        except (json.JSONDecodeError, TypeError):
            pkg = {}
        if isinstance(pkg, dict):
            names = set()
            for section in ("dependencies", "devDependencies", "peerDependencies"):
                block = pkg.get(section)
                if isinstance(block, dict):
                    names.update(block)
            for name in names:
                label = _match_dependency(name)
                if label:
                    found.add(label)
            # A package.json at all means the Node toolchain.
            found.add("Node.js")

    for entry in root_entries:
        label = FILE_SIGNALS.get(entry.lower())
        if label:
            found.add(label)

    return found


def rank(per_repo: list[set[str]], exclude: set[str] | None = None) -> list[Technology]:
    """Count technologies across repositories, most widely used first."""
    exclude = {e.lower() for e in (exclude or set())}
    counts: dict[str, int] = {}
    for repo in per_repo:
        for tech in repo:
            if tech.lower() in exclude:
                continue
            counts[tech] = counts.get(tech, 0) + 1
    return [
        Technology(name, n)
        for name, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
