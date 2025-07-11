# Unified Scraper Service - Render Deployment

A single FastAPI service that combines GitHub and LinkedIn scraping capabilities, optimized for deployment on Render.com.

## 🚀 Quick Deploy to Render

### 1. Prerequisites

- GitHub repository with this `deploy/` folder
- GitHub Personal Access Token
- LinkedIn account credentials

### 2. Deploy Steps

#### Option A: One-Click Deploy

1. **Fork this repository** or copy the `deploy/` folder to your repo
2. **Create a new Web Service** on [Render](https://render.com)
3. **Connect your GitHub repo** and select the `deploy/` folder as root directory
4. **Set Environment Variables** (see below)
5. **Deploy!** Render will automatically build and deploy

#### Option B: Manual Configuration

1. Create new Web Service on Render
2. Repository: `your-username/your-repo`
3. Root Directory: `deploy/`
4. Runtime: `Docker`
5. Dockerfile Path: `./Dockerfile`

### 3. Required Environment Variables

Set these in your Render dashboard under Environment:

```bash
GITHUB_TOKEN=ghp_your_github_token_here
LINKEDIN_EMAIL=your-email@example.com
LINKEDIN_PASSWORD=your-linkedin-password
```

### 3.5. Email Verification Automation (Recommended)

To enable automatic email verification code handling:

```bash
# Email automation credentials
EMAIL_PASSWORD=your-email-app-password
# OR
EMAIL_APP_PASSWORD=your-email-app-password
```

**⚠️ Important Email Setup:**

**For Gmail:**
1. Enable 2-Factor Authentication
2. Generate App Password: [Google Account Settings](https://myaccount.google.com/apppasswords)
3. Use the 16-character app password (not your regular password)

**For Outlook/Hotmail:**
1. Enable 2-Factor Authentication
2. Generate App Password: [Microsoft Account Security](https://account.microsoft.com/security)
3. Use the generated app password

**For Yahoo:**
1. Enable 2-Factor Authentication
2. Generate App Password: [Yahoo Account Security](https://account.yahoo.com/account/security)
3. Use the generated app password

**Supported Email Providers:**
- ✅ Gmail (gmail.com)
- ✅ Outlook (outlook.com, hotmail.com, live.com)
- ✅ Yahoo (yahoo.com, ymail.com)
- ✅ AOL (aol.com)
- ✅ iCloud (icloud.com, me.com, mac.com)
- ✅ Custom IMAP servers

### 4. Bright Data Proxy Configuration (Recommended for Production)

To avoid IP blocks and improve scraping reliability, configure Bright Data rotating proxies:

```bash
# Bright Data proxy settings (optional - defaults provided)
BRIGHTDATA_PROXY_HOST=brd.superproxy.io
BRIGHTDATA_PROXY_PORT=33335
BRIGHTDATA_PROXY_USER=brd-customer-hl_37fca7c2-zone-linkedin_scraper
BRIGHTDATA_PROXY_PASS=xo5nwe0e1bt2
```

**Note**: The proxy credentials above are examples. For production use:

1. Sign up for [Bright Data](https://brightdata.com)
2. Create a "LinkedIn Scraper" zone
3. Replace the credentials with your actual zone credentials

### 5. Optional Environment Variables

```bash
PYTHONUNBUFFERED=1
DISPLAY=:99
MAX_WORKERS=10
```

## 📡 API Endpoints

Once deployed, your service will be available at `https://your-app-name.onrender.com`

### Health Checks

```bash
GET /health                # Overall service health
GET /github/health         # GitHub scraper health
GET /linkedin/health       # LinkedIn scraper health
```

### GitHub Scraping

```bash
POST /github/scrape
{
    "applicant_id": "12345",
    "github_url": "https://github.com/username"
}
```

### LinkedIn Scraping

```bash
POST /linkedin/scrape
{
    "applicant_id": "12345",
    "linkedin_url": "https://linkedin.com/in/username",
    "email": "optional@email.com",
    "password": "optional_password"
}
```

### API Documentation

- Interactive docs: `https://your-app.onrender.com/docs`
- Alternative docs: `https://your-app.onrender.com/redoc`

## 🏗️ Architecture

### Service Components

- **FastAPI Application**: Main web service
- **GitHub Scraper**: Lightweight API-based scraping
- **LinkedIn Scraper**: Browser-based scraping with Chrome + Bright Data proxy
- **Chrome + Selenium**: Headless browser for LinkedIn with rotating IP support
- **Bright Data Proxy**: Rotating residential IPs to avoid blocks (optional)
- **Gunicorn**: Production WSGI server

### Resource Requirements

- **Memory**: 2GB (for Chrome browser)
- **CPU**: 1 core minimum
- **Storage**: 10GB for browser cache and dependencies
- **Plan**: Render Standard plan recommended

### Performance

- **GitHub Scraping**: ~2-5 seconds response time
- **LinkedIn Scraping**: ~30-60 seconds response time
- **Concurrent Requests**: 2 workers by default

## 🔧 Configuration Files

### Files in this deployment folder:

- `app.py` - Main FastAPI application
- `Github_Scraper.py` - GitHub scraping logic
- `LinkedIn_Scraper.py` - LinkedIn scraping logic
- `skillExtractionExtra.py` - Additional LinkedIn utilities
- `requirements.txt` - Python dependencies
- `Dockerfile` - Container configuration
- `render.yaml` - Render service configuration
- `start.sh` - Alternative startup script
- `environment.example` - Environment variables template

## 🐛 Troubleshooting

### Common Issues

#### Deployment Fails

- **Build timeout**: Increase build timeout in Render settings
- **Memory issues**: Upgrade to Standard plan
- **Chrome installation**: Check Dockerfile Chrome dependencies

#### Service Not Starting

- **Port binding**: Render automatically sets PORT environment variable
- **Health check fails**: Verify `/health` endpoint is accessible
- **Chrome not found**: Check browser installation in logs

#### Scraping Issues

- **GitHub 401**: Verify GITHUB_TOKEN is valid and has correct permissions
- **LinkedIn login fails**: Check credentials and account status
- **LinkedIn security challenges**: Check logs for challenge type (2FA, CAPTCHA, etc.)
- **IP blocks**: Configure Bright Data proxy or try different LinkedIn account
- **Timeout errors**: LinkedIn scraping may take 30-60 seconds
- **Proxy connection fails**: Verify Bright Data credentials and zone configuration

#### Email Verification Issues

- **Email connection failed**: Verify app password (not regular password) is used
- **No verification code found**: Check email arrives within 5 minutes, verify LinkedIn sends to correct email
- **Auto-fill failed**: Manual intervention will be available as fallback
- **IMAP not supported**: Ensure email provider supports IMAP access
- **Authentication errors**: Enable 2FA and generate fresh app password

### Debug Commands

Check logs in Render dashboard or via CLI:

```bash
# Check service status
curl https://your-app.onrender.com/health

# Test GitHub scraper
curl -X POST "https://your-app.onrender.com/github/scrape" \
  -H "Content-Type: application/json" \
  -d '{"applicant_id": "test", "github_url": "https://github.com/octocat"}'

# Test LinkedIn scraper
curl -X POST "https://your-app.onrender.com/linkedin/scrape" \
  -H "Content-Type: application/json" \
  -d '{"applicant_id": "test", "linkedin_url": "https://linkedin.com/in/test"}'
```

## 📊 Usage Examples

### Python Client

```python
import requests

BASE_URL = "https://your-app.onrender.com"

# GitHub scraping
response = requests.post(f"{BASE_URL}/github/scrape", json={
    "applicant_id": "12345",
    "github_url": "https://github.com/username"
})
print(response.json())

# LinkedIn scraping
response = requests.post(f"{BASE_URL}/linkedin/scrape", json={
    "applicant_id": "12345",
    "linkedin_url": "https://linkedin.com/in/username"
})
print(response.json())

# LinkedIn scraping with email verification
response = requests.post(f"{BASE_URL}/linkedin/scrape", json={
    "applicant_id": "12345",
    "linkedin_url": "https://linkedin.com/in/username",
    "email_password": "your-email-app-password",  # Optional: if not in env
    "enable_email_verification": True
})
print(response.json())
```

### JavaScript Client

```javascript
const BASE_URL = "https://your-app.onrender.com";

// GitHub scraping
const githubResponse = await fetch(`${BASE_URL}/github/scrape`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    applicant_id: "12345",
    github_url: "https://github.com/username",
  }),
});
const githubData = await githubResponse.json();

// LinkedIn scraping
const linkedinResponse = await fetch(`${BASE_URL}/linkedin/scrape`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    applicant_id: "12345",
    linkedin_url: "https://linkedin.com/in/username",
  }),
});
const linkedinData = await linkedinResponse.json();
```

## 🔐 Security Considerations

### Environment Variables

- Never commit credentials to your repository
- Use Render's environment variable management
- Rotate tokens and passwords regularly

### API Security

- Consider adding API authentication for production use
- Implement rate limiting for public endpoints
- Monitor usage for abuse

### LinkedIn Compliance

- Respect LinkedIn's terms of service
- Implement appropriate delays between requests
- Consider using LinkedIn's official APIs when possible

## 📈 Monitoring & Scaling

### Health Monitoring

- Render automatically monitors `/health` endpoint
- Set up alerts for service downtime
- Monitor response times and error rates

### Scaling Options

```yaml
# In render.yaml, adjust:
services:
  - type: web
    plan: standard # or pro for more resources
    autoDeploy: true
    scaling:
      minInstances: 1
      maxInstances: 3
```

### Performance Optimization

- Use caching for frequently scraped profiles
- Implement request queuing for high load
- Consider separating GitHub and LinkedIn into microservices for heavy usage

## 🔄 Updates & Maintenance

### Updating the Service

1. Push changes to your GitHub repository
2. Render auto-deploys on git push (if enabled)
3. Monitor deployment logs for issues

### Dependency Updates

- Update `requirements.txt` as needed
- Test changes locally before deploying
- Chrome/ChromeDriver versions are managed automatically

## 💡 Tips for Production

1. **Use Standard Plan**: Free tier has limitations for Chrome
2. **Set Timeouts**: LinkedIn scraping can take time
3. **Monitor Resources**: Watch memory usage with Chrome
4. **Error Handling**: Implement proper retry logic
5. **Logging**: Use Render's logging for debugging
6. **Backup Strategy**: Keep environment variables documented

## 📞 Support

For deployment issues:

1. Check Render documentation
2. Review service logs in Render dashboard
3. Test endpoints manually
4. Verify environment variables are set correctly

## 🎯 Next Steps

After successful deployment:

1. Test all endpoints thoroughly
2. Set up monitoring and alerts
3. Document your API for team usage
4. Consider implementing authentication
5. Scale resources based on usage patterns

Your unified scraper service is now ready for production use on Render! 🚀
