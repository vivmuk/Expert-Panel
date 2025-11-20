# Railway Deployment Guide

This guide walks you through deploying the AI Expert Panel application to Railway.

## Prerequisites

1. A Railway account (sign up at https://railway.app)
2. Your GitHub repository connected to Railway
3. Venice AI API key

## Deployment Steps

### 1. Prepare Your Repository

Your repository is already configured with:
- ✅ `requirements.txt` - Python dependencies
- ✅ `Procfile` - Process configuration (uses `$PORT`)
- ✅ `railway.json` - Railway configuration
- ✅ `app.py` - Flask application entry point

### 2. Create a New Project on Railway

1. Go to https://railway.app
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Choose your repository: `vivmuk/Expert-Panel`
5. Railway will automatically detect it's a Python app

### 3. Configure Environment Variables

Railway will need the following environment variables:

#### Required:
- `VENICE_API_KEY` - Your Venice AI API key
  - Value: `ntmhtbP2fr_pOQsmuLPuN_nm6lm2INWKiNcvrdEfEC`

#### Optional (with defaults):
- `PORT` - Automatically set by Railway (default: 5000)
- `FLASK_ENV` - Environment mode (default: `production`)
- `FLASK_DEBUG` - Debug mode (default: `False`)

**To set environment variables:**
1. In your Railway project, go to **Variables** tab
2. Click **"New Variable"**
3. Add each variable:
   - Key: `VENICE_API_KEY`
   - Value: `ntmhtbP2fr_pOQsmuLPuN_nm6lm2INWKiNcvrdEfEC`
   - Click **"Add"**

### 4. Configure Build Settings (Optional)

Railway will automatically:
- Detect Python from `requirements.txt`
- Use `Procfile` for the start command
- Set `PORT` environment variable
- Run health checks on `/health` endpoint

If you want to customize, you can:
1. Go to **Settings** → **Build**
2. Verify these settings:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: (from Procfile) `gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 600 --keep-alive 2 --max-requests 1000 --max-requests-jitter 50 --preload app:app`

### 5. Deploy

1. Railway will automatically deploy on push to the main branch
2. Watch the deployment logs in the **Deployments** tab
3. Once deployed, Railway will provide a public URL (e.g., `https://your-app.up.railway.app`)

### 6. Configure Custom Domain (Optional)

1. Go to **Settings** → **Networking**
2. Click **"Generate Domain"** or **"Add Custom Domain"**
3. Follow the DNS configuration instructions

### 7. Update Frontend Configuration

Update your frontend to use the Railway URL:

In `index.html`, update the `BACKEND_URL`:
```javascript
const BACKEND_URL = window.location.hostname === 'localhost' ? 
    'http://127.0.0.1:5000' : 
    'https://your-app.up.railway.app';
```

## Health Check

Railway will automatically check the `/health` endpoint:
- Endpoint: `GET /health`
- Expected response: `200 OK` with JSON health status

## Monitoring

Railway provides:
- **Metrics** - CPU, Memory, Network usage
- **Logs** - Real-time application logs
- **Deployments** - Deployment history
- **Events** - Application events and errors

## Troubleshooting

### Build Fails
- Check that all dependencies in `requirements.txt` are valid
- Verify Python version compatibility (Railway uses Python 3.11+)
- Check build logs for specific errors

### Application Won't Start
- Verify `PORT` environment variable is being used (Railway sets this automatically)
- Check that `gunicorn` is in `requirements.txt` ✅
- Review application logs in Railway dashboard

### API Calls Fail
- Verify `VENICE_API_KEY` environment variable is set correctly
- Check CORS settings (already configured for all origins)
- Review API response in application logs

### High Memory Usage
- Adjust `--workers` in Procfile (currently 2)
- Consider using `--worker-class gevent` for async handling
- Monitor memory usage in Railway metrics

## Scaling

Railway automatically scales based on traffic. To manually scale:
1. Go to **Settings** → **Scaling**
2. Adjust resources (CPU, Memory) as needed
3. Railway will handle load balancing automatically

## Cost Optimization

- Railway offers a free tier with $5/month credit
- Monitor usage in the Railway dashboard
- Optimize worker count and timeout settings in Procfile
- Use caching for repeated API calls (already implemented)

## Continuous Deployment

Railway automatically deploys on:
- Push to main/master branch
- Merge to main/master branch

To disable auto-deploy:
1. Go to **Settings** → **Service**
2. Uncheck **"Auto Deploy"**

## Rollback

To rollback to a previous deployment:
1. Go to **Deployments** tab
2. Find the deployment you want to restore
3. Click the **"..."** menu → **"Redeploy"**

## Security

- Never commit API keys to Git (use environment variables)
- Railway automatically provides HTTPS
- CORS is configured for all origins (adjust if needed)
- Rate limiting is already implemented (`@limiter.limit`)

## Support

- Railway Docs: https://docs.railway.app
- Railway Discord: https://discord.gg/railway
- Check application logs in Railway dashboard

---

**Your app is ready for Railway!** 🚀

Just follow the steps above and your Expert Panel will be live in minutes.

