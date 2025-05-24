# AI Expert Panel - Deployment Guide

## Quick Deployment to Netlify + Render

### 1. Deploy Backend to Render

1. Push your code to GitHub (create a new repository)
2. Go to [render.com](https://render.com) and sign up
3. Create "New Web Service" → "Build and deploy from a Git repository"
4. Select your GitHub repository
5. Configure:
   - **Name**: `ai-expert-panel-backend`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Instance Type**: Free

### 2. Update Frontend with Backend URL

1. Once Render deployment is complete, copy your backend URL (e.g., `https://ai-expert-panel-backend-xyz.onrender.com`)
2. Edit `frontend/index.html` line 717:
   ```javascript
   'https://YOUR_RENDER_BACKEND_URL.onrender.com';
   ```
   Replace with your actual Render URL.

### 3. Deploy Frontend to Netlify

1. Go to [netlify.com](https://netlify.com) and sign up
2. **Option A - Drag & Drop**: Drag the `frontend` folder to Netlify dashboard
3. **Option B - Git**: Connect repository and set "Publish directory" to `frontend`

### 4. Test Your Live Site

- Visit your Netlify URL
- Sign in with Google
- Test creating a report
- Save and retrieve reports

## Environment Variables

Make sure your Render backend has these environment variables set if needed:
- Any API keys should be added via Render's Environment Variables section
- The Venice AI API key is currently hardcoded in `app.py` (line 4)

## Domain (Optional)

- **Netlify**: Free custom domain via Netlify
- **Render**: Custom domain available on paid plans

## Monitoring

- **Render**: View logs in the Render dashboard
- **Netlify**: View function logs and analytics in Netlify dashboard

## Troubleshooting

1. **CORS Issues**: Ensure your Render backend allows your Netlify domain
2. **API Errors**: Check Render logs for Python errors
3. **Firebase Auth**: Ensure Firebase config is correct in frontend

---

Your site will be live at: `https://your-app-name.netlify.app` 

Try this in your browser console:
```javascript
fetch('https://expert-panel.onrender.com/test', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({test: 'data'})
}).then(r => r.json()).then(console.log)
``` 