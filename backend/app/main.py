from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.routers import auth, health, checkins, plans, projects, reviews, rules
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="CommandPilot API",
    description="Personal Operating System for ambitious people",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000"],
    # Covers all Vercel preview deployments for this project/team.
    # Exact pattern: command-pilot-<hash>-serkans-projects-a49183cd.vercel.app
    allow_origin_regex=r"^https://command-pilot-[a-z0-9-]+-serkans-projects-a49183cd\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(checkins.router, prefix="/api/checkins", tags=["checkins"])
app.include_router(plans.router, prefix="/api/plans", tags=["plans"])
app.include_router(reviews.router, prefix="/api/reviews", tags=["reviews"])
app.include_router(rules.router, prefix="/api/rules", tags=["rules"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
