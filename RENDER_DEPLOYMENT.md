# Render Deployment Guide - Python Runtime

This guide shows how to deploy the unified scraper service to Render using Python runtime with uvicorn.

## 🚀 Quick Deploy

### Method 1: Deploy via GitHub (Recommended)

1. **Push to GitHub**

   ```bash
   git add deploy/
   git commit -m "Add Render deployment files"
   git push origin main
   ```

2. **Create Render Service**

   - Go to [Render Dashboard](https://dashboard.render.com)
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Select the repository containing your code

3. **Configure Service**

   - **Name**: `unified-scraper` (or any name you prefer)
   - **Runtime**: `Python 3`
   - **Root Directory**: `deploy`
   - **Build Command**: `pip install --upgrade pip && pip install -r requirements.txt`
   - **Start Command**: `uvicorn app:app --host 0.0.0.0 --port $PORT --workers 2`

4. **Set Environment Variables**

   ```
   GITHUB_TOKEN=your_github_token_here
   LINKEDIN_EMAIL=your_linkedin_email_here
   LINKEDIN_PASSWORD=your_linkedin_password_here
   PYTHONUNBUFFERED=1
   ```

5. **Deploy**
   - Click "Create Web Service"
   - Wait for deployment to complete (~5-10 minutes)

### Method 2: Deploy via render.yaml

1. Place the `deploy/` folder contents in your repository root
2. Ensure `render.yaml` is in the root directory
3. Connect to Render and it will auto-detect the configuration

## 📁 Deployment Structure

```
deploy/
├── app.py                 # Main FastAPI application
├── Github_Scraper.py      # GitHub scraping module
├── LinkedIn_Scraper.py    # LinkedIn scraping module
├── requirements.txt       # Python dependencies
├── render.yaml           # Render configuration
├── requirements-stable.txt # Alternative stable versions
├── app-stable.py         # Alternative app with pydantic v1
└── RENDER_DEPLOYMENT.md  # This deployment guide
```

## 🔧 Configuration Details

### Python Runtime Configuration

- **Runtime**: Python 3.11+ (Render's default)
- **Package Manager**: pip
- **Web Server**: uvicorn (ASGI server)
- **Workers**: 2 (can be adjusted based on needs)

### Environment Variables

All environment variables are required for proper operation:

| Variable            | Description                  | Required        |
| ------------------- | ---------------------------- | --------------- |
| `GITHUB_TOKEN`      | GitHub Personal Access Token | Yes             |
| `LINKEDIN_EMAIL`    | LinkedIn account email       | Yes             |
| `LINKEDIN_PASSWORD` | LinkedIn account password    | Yes             |
| `PYTHONUNBUFFERED`  | Python output buffering      | No (set to "1") |

### Chrome/Selenium Setup

The LinkedIn scraper uses Chrome in headless mode:

- Chrome binary is available in Render's Python environment
- webdriver-manager automatically downloads chromedriver
- No additional Chrome installation needed

## 🔗 Service Endpoints

Once deployed, your service will be available at `https://your-service-name.onrender.com`

### Health Checks

- `GET /health` - Overall service health
- `GET /github/health` - GitHub scraper health
- `GET /linkedin/health` - LinkedIn scraper health

### Scraping Endpoints

- `POST /github/scrape` - Scrape GitHub profile
- `POST /linkedin/scrape` - Scrape LinkedIn profile

### Legacy Endpoints (backward compatibility)

- `POST /scrape/github` - Legacy GitHub endpoint
- `POST /scrape/linkedin` - Legacy LinkedIn endpoint

## 📝 Request Examples

### GitHub Scraping

```bash
curl -X POST "https://your-service.onrender.com/github/scrape" \
     -H "Content-Type: application/json" \
     -d '{
       "applicant_id": "123",
       "github_url": "https://github.com/username"
     }'
```

### LinkedIn Scraping

```bash
curl -X POST "https://your-service.onrender.com/linkedin/scrape" \
     -H "Content-Type: application/json" \
     -d '{
       "applicant_id": "123",
       "linkedin_url": "https://linkedin.com/in/username"
     }'
```

## 🚨 Troubleshooting

### Common Issues

1. **Build Failures**

   - Check if all dependencies in `requirements.txt` are compatible
   - Use `requirements-stable.txt` if pydantic v2 causes issues

2. **Chrome/Selenium Issues**

   - LinkedIn scraper requires Chrome for web scraping
   - Chrome is pre-installed in Render's Python environment
   - If issues persist, check logs for webdriver errors

3. **Authentication Errors**

   - Verify all environment variables are set correctly
   - Test credentials manually before deployment

4. **Timeout Issues**
   - Render has request timeouts (30s default)
   - LinkedIn scraping might take longer for complex profiles
   - Consider implementing timeout handling in your client

### Alternative Stable Deployment

If you encounter pydantic v2 compatibility issues:

1. **Use Stable Requirements**

   ```bash
   # In deploy/ directory
   cp requirements-stable.txt requirements.txt
   cp app-stable.py app.py
   ```

2. **Redeploy**
   - Commit changes and push to trigger redeploy
   - Or manually trigger deploy from Render dashboard

## 📊 Performance

### Resource Usage

- **Memory**: ~512MB baseline + Chrome overhead
- **CPU**: Moderate usage during scraping operations
- **Storage**: ~200MB for dependencies + Chrome
- **Network**: Depends on scraping frequency

### Scaling Recommendations

- **Free Plan**: Suitable for testing and light usage
- **Starter Plan**: Recommended for production use
- **Standard Plan**: For high-volume scraping

## 🔒 Security Notes

1. **Environment Variables**: Never commit sensitive credentials to code
2. **LinkedIn Credentials**: Use dedicated account for scraping
3. **GitHub Token**: Use minimal permissions (public repo access)
4. **Rate Limiting**: Be mindful of LinkedIn/GitHub rate limits

## 📖 Additional Resources

- [Render Documentation](https://render.com/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Selenium Documentation](https://selenium-python.readthedocs.io/)

## 🆘 Support

If you encounter issues:

1. Check Render service logs for detailed error messages
2. Test endpoints individually using the `/health` endpoints
3. Verify environment variables are set correctly
4. Check this README for common troubleshooting steps
