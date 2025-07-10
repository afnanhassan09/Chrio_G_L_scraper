from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, Union
import os
from dotenv import load_dotenv
import sys
import traceback

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import scrapers (flattened structure)
import Github_Scraper
import LinkedIn_Scraper

# Load environment variables
load_dotenv()

app = FastAPI(
    title="Unified Scraper Service",
    version="1.0.0",
    description="Combined GitHub and LinkedIn scraper service with separate endpoints",
)


# Request Models
class GitHubScrapeRequest(BaseModel):
    applicant_id: str
    github_url: str


class LinkedInScrapeRequest(BaseModel):
    applicant_id: str
    linkedin_url: str
    email: Optional[str] = None
    password: Optional[str] = None
    email_password: Optional[str] = None
    enable_email_verification: Optional[bool] = True


# Response Models
class GitHubScrapeResponse(BaseModel):
    id: str
    source: str
    data: list


class LinkedInScrapeResponse(BaseModel):
    id: str
    source: str
    data: Dict[str, Any]


class HealthResponse(BaseModel):
    status: str
    service: str
    available_endpoints: Dict[str, str]


# Health Check Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Overall health check endpoint"""
    return HealthResponse(
        status="healthy",
        service="unified-scraper",
        available_endpoints={
            "github_health": "/github/health",
            "linkedin_health": "/linkedin/health",
            "github_scrape": "/github/scrape",
            "linkedin_scrape": "/linkedin/scrape",
        },
    )


@app.get("/github/health")
async def github_health_check():
    """GitHub scraper health check"""
    token = os.getenv("GITHUB_TOKEN")
    return {
        "status": "healthy" if token else "configuration_error",
        "service": "github-scraper",
        "token_configured": bool(token),
    }


@app.get("/linkedin/health")
async def linkedin_health_check():
    """LinkedIn scraper health check"""
    email = os.getenv("LINKEDIN_EMAIL")
    password = os.getenv("LINKEDIN_PASSWORD")
    email_password = os.getenv("EMAIL_PASSWORD") or os.getenv("EMAIL_APP_PASSWORD")

    return {
        "status": "healthy" if (email and password) else "configuration_error",
        "service": "linkedin-scraper",
        "credentials_configured": bool(email and password),
        "email_verification_available": bool(email_password),
        "features": {
            "basic_scraping": bool(email and password),
            "automatic_email_verification": bool(email_password),
            "manual_verification_fallback": True,
        },
    }


# GitHub Scraper Routes
@app.post("/github/scrape", response_model=GitHubScrapeResponse)
async def scrape_github_profile(request: GitHubScrapeRequest):
    """
    Scrape GitHub profile data for a given applicant
    """
    try:
        # Validate that GitHub token is available
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise HTTPException(
                status_code=500,
                detail="GitHub token not configured. Please set GITHUB_TOKEN environment variable.",
            )

        # Call the scraper function
        result = Github_Scraper.scrape_github_profile(
            request.applicant_id, request.github_url
        )

        return GitHubScrapeResponse(**result)

    except Exception as e:
        print(f"GitHub scraping error: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail=f"Error scraping GitHub profile: {str(e)}"
        )


# LinkedIn Scraper Routes
@app.post("/linkedin/scrape", response_model=LinkedInScrapeResponse)
async def scrape_linkedin_profile(request: LinkedInScrapeRequest):
    """
    Scrape LinkedIn profile data for a given applicant
    """
    try:
        # Use provided credentials or fall back to environment variables
        email = request.email or os.getenv("LINKEDIN_EMAIL")
        password = request.password or os.getenv("LINKEDIN_PASSWORD")

        if not email or not password:
            raise HTTPException(
                status_code=500,
                detail="LinkedIn credentials not configured. Please provide email/password or set LINKEDIN_EMAIL/LINKEDIN_PASSWORD environment variables.",
            )
        print(request)
        # Call the scraper function with email verification support
        result = LinkedIn_Scraper.scrape_linkedin_profile(
            applicant_id=request.applicant_id,
            profile_url=request.linkedin_url,
            email=email,
            password=password,
            email_password=request.email_password,
            enable_email_verification=request.enable_email_verification,
        )

        return LinkedInScrapeResponse(**result)

    except Exception as e:
        print(f"LinkedIn scraping error: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail=f"Error scraping LinkedIn profile: {str(e)}"
        )


# Legacy Routes (for backward compatibility)
@app.post("/scrape/github", response_model=GitHubScrapeResponse)
async def legacy_github_scrape(request: GitHubScrapeRequest):
    """Legacy GitHub scrape endpoint for backward compatibility"""
    return await scrape_github_profile(request)


@app.post("/scrape/linkedin", response_model=LinkedInScrapeResponse)
async def legacy_linkedin_scrape(request: LinkedInScrapeRequest):
    """Legacy LinkedIn scrape endpoint for backward compatibility"""
    return await scrape_linkedin_profile(request)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": "Unified Scraper API",
        "version": "1.0.0",
        "description": "Combined GitHub and LinkedIn scraper service",
        "platform": "Render",
        "endpoints": {
            "health": "/health",
            "github": {"health": "/github/health", "scrape": "/github/scrape"},
            "linkedin": {"health": "/linkedin/health", "scrape": "/linkedin/scrape"},
            "docs": "/docs",
            "redoc": "/redoc",
        },
        "legacy_endpoints": {
            "github_scrape": "/scrape/github",
            "linkedin_scrape": "/scrape/linkedin",
        },
    }


# Development endpoint for testing
@app.get("/test")
async def test_endpoint():
    """Test endpoint to verify service is running"""
    return {
        "message": "Unified scraper service is running on Render!",
        "github_token_set": bool(os.getenv("GITHUB_TOKEN")),
        "linkedin_email_set": bool(os.getenv("LINKEDIN_EMAIL")),
        "linkedin_password_set": bool(os.getenv("LINKEDIN_PASSWORD")),
        "render_deployment": True,
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
