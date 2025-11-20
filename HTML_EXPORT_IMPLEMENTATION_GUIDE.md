# HTML Export Implementation Guide

This guide provides step-by-step instructions for implementing a professional, navigable HTML export feature similar to the one used in AI Pathway V3. The export creates a standalone, print-friendly HTML document with smooth navigation.

---

## Overview

The HTML export feature:
- Generates a complete standalone HTML file (no external dependencies)
- Includes professional consulting-style design (BCG/McKinsey inspired)
- Provides clickable navigation (table of contents, back-to-top links)
- Features a floating home button for easy navigation
- Is print-friendly with proper page breaks
- Uses smooth scrolling for better UX

---

## Core Components

### 1. Export Function Structure

```javascript
function exportToHTML() {
    // 1. Generate HTML content
    const htmlContent = generateExportHTML();
    
    // 2. Create blob and download
    const blob = new Blob([htmlContent], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    
    // 3. Trigger download
    const a = document.createElement('a');
    a.href = url;
    a.download = 'Your_Document_Name.html';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}
```

### 2. HTML Generation Function

```javascript
function generateExportHTML() {
    const data = yourDataObject; // Your data structure
    
    // Build HTML sections
    const coverPage = buildCoverPage(data);
    const tableOfContents = buildTableOfContents(data);
    const contentSections = buildContentSections(data);
    
    // Combine into complete HTML
    return `
<!DOCTYPE html>
<html lang="en">
<head>
    ${buildHeadSection(data)}
</head>
<body>
    ${coverPage}
    ${tableOfContents}
    ${contentSections}
    ${buildFloatingHomeButton()}
</body>
</html>
    `;
}
```

---

## Step-by-Step Implementation

### Step 1: Create Helper Functions

#### HTML Escaping Function
**Critical for security** - Always escape user-generated content:

```javascript
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}
```

#### Text Formatting Function
Converts plain text to HTML with proper paragraph breaks:

```javascript
function formatText(text) {
    if (!text) return '';
    return String(text)
        .replace(/\n\n+/g, '</p><p>')  // Double newlines = paragraphs
        .replace(/\n/g, '<br>')         // Single newlines = line breaks
        .replace(/^/, '<p>')
        .replace(/$/, '</p>');
}
```

### Step 2: Build Table of Contents

**Key Features:**
- Clickable links to each section
- Unique IDs for each section
- Hover effects for better UX

```javascript
function buildTableOfContents(data) {
    // Example: If you have chapters/sections
    const tocItems = data.sections.map((section, index) => `
        <a href="#section-${section.id}" class="toc-item">
            <span class="toc-number">${index + 1}</span>
            <span class="toc-title-text">${escapeHtml(section.title)}</span>
        </a>
    `).join('');
    
    return `
        <div class="toc-section" id="toc">
            <h2 class="toc-title">Table of Contents</h2>
            ${tocItems}
        </div>
    `;
}
```

**Important:** Each section must have a matching ID:
```html
<div id="section-1" class="content-section">
    <!-- Content here -->
</div>
```

### Step 3: Build Content Sections

**Pattern:** Map over your data structure and generate HTML for each item:

```javascript
function buildContentSections(data) {
    return data.sections.map((section, index) => `
        <div class="content-section" id="section-${section.id}">
            <div class="section-header">
                <h1 class="section-title">${escapeHtml(section.title)}</h1>
                ${section.subtitle ? `<p class="section-subtitle">${escapeHtml(section.subtitle)}</p>` : ''}
            </div>
            
            ${section.introduction ? `
                <div class="content-block">
                    <h2>Introduction</h2>
                    <div class="content-text">${formatText(escapeHtml(section.introduction))}</div>
                </div>
            ` : ''}
            
            ${section.items && section.items.length ? `
                <div class="content-block">
                    <h2>Items</h2>
                    ${section.items.map(item => `
                        <div class="item-box">
                            <h3>${escapeHtml(item.title)}</h3>
                            <p>${formatText(escapeHtml(item.description))}</p>
                        </div>
                    `).join('')}
                </div>
            ` : ''}
            
            <!-- Navigation link back to TOC -->
            <div class="section-navigation">
                <a href="#toc" class="back-to-top-link">↑ Back to Table of Contents</a>
            </div>
            
            ${index < data.sections.length - 1 ? '<div class="page-break"></div>' : ''}
        </div>
    `).join('');
}
```

### Step 4: Build CSS Styles

**Design Principles:**
- Clean, professional look (white background, dark text)
- Good typography (use a professional font like Montserrat)
- Proper spacing and hierarchy
- Print-friendly styles

```css
/* Base Styles */
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    font-family: 'Montserrat', sans-serif;
    line-height: 1.7;
    color: #1a1a1a;
    background: #ffffff;
    font-size: 14px;
}

.document-container {
    max-width: 900px;
    margin: 0 auto;
    padding: 60px 50px;
    background: white;
}

/* Table of Contents Styles */
.toc-section {
    margin: 60px 0;
    padding: 40px 0;
    border-top: 1px solid #e0e0e0;
    border-bottom: 1px solid #e0e0e0;
}

.toc-item {
    display: flex;
    align-items: flex-start;
    padding: 12px 0;
    border-bottom: 1px solid #f0f0f0;
    text-decoration: none;
    color: inherit;
    transition: background-color 0.2s ease;
}

.toc-item:hover {
    background-color: #f8f9fa;
    padding-left: 8px;
    padding-right: 8px;
    margin-left: -8px;
    margin-right: -8px;
}

/* Content Section Styles */
.content-section {
    margin: 80px 0;
}

.section-header {
    border-bottom: 2px solid #1a1a1a;
    padding-bottom: 20px;
    margin-bottom: 40px;
}

.section-title {
    font-size: 32px;
    font-weight: 700;
    color: #1a1a1a;
    margin-bottom: 12px;
}

/* Navigation Link Styles */
.section-navigation {
    margin-top: 60px;
    padding-top: 30px;
    border-top: 1px solid #e0e0e0;
    text-align: center;
}

.back-to-top-link {
    display: inline-block;
    padding: 12px 24px;
    background: #f8f9fa;
    color: #1a1a1a;
    text-decoration: none;
    border-radius: 4px;
    font-weight: 600;
    font-size: 14px;
    transition: all 0.2s ease;
    border: 1px solid #e0e0e0;
}

.back-to-top-link:hover {
    background: #1a1a1a;
    color: #ffffff;
    border-color: #1a1a1a;
}

/* Floating Home Button */
.floating-home {
    position: fixed;
    bottom: 30px;
    right: 30px;
    width: 50px;
    height: 50px;
    background: #1a1a1a;
    color: #ffffff;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    text-decoration: none;
    font-size: 20px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    transition: all 0.3s ease;
    z-index: 1000;
}

.floating-home:hover {
    background: #4a4a4a;
    transform: scale(1.1);
    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
}

/* Smooth Scrolling */
html {
    scroll-behavior: smooth;
}

/* Print Styles */
@media print {
    .floating-home {
        display: none;
    }
    .page-break {
        page-break-before: always;
    }
    body {
        background: white;
    }
}
```

### Step 5: Build Complete HTML Template

```javascript
function generateExportHTML() {
    const data = yourDataObject;
    const generatedDate = new Date().toLocaleDateString('en-US', { 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric' 
    });
    
    return `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${escapeHtml(data.title)}</title>
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        ${getCSSStyles()}  // Include all CSS from Step 4
    </style>
</head>
<body>
    <div class="document-container">
        ${buildCoverPage(data, generatedDate)}
        ${buildTableOfContents(data)}
        ${buildContentSections(data)}
    </div>
    
    <a href="#toc" class="floating-home" title="Back to Table of Contents">⌂</a>
</body>
</html>
    `;
}
```

---

## Key Patterns & Best Practices

### 1. Conditional Rendering
Always check if data exists before rendering:

```javascript
${section.description ? `
    <div class="description">${formatText(escapeHtml(section.description))}</div>
` : ''}
```

### 2. Array Mapping
Use `.map()` to generate repeated elements:

```javascript
${items.map(item => `
    <div class="item">${escapeHtml(item.name)}</div>
`).join('')}
```

### 3. Unique IDs
Ensure each section has a unique ID matching TOC links:

```javascript
// TOC link
<a href="#section-${section.id}">...</a>

// Section
<div id="section-${section.id}">...</div>
```

### 4. Security
**Always escape user-generated content:**

```javascript
// ❌ BAD - XSS vulnerability
<div>${userInput}</div>

// ✅ GOOD - Safe
<div>${escapeHtml(userInput)}</div>
```

### 5. Text Formatting
Use `formatText()` for multi-line text to preserve formatting:

```javascript
// Preserves paragraphs and line breaks
<div>${formatText(escapeHtml(multiLineText))}</div>
```

---

## Complete Example Implementation

Here's a complete, minimal example you can adapt:

```javascript
// Helper Functions
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

function formatText(text) {
    if (!text) return '';
    return String(text)
        .replace(/\n\n+/g, '</p><p>')
        .replace(/\n/g, '<br>')
        .replace(/^/, '<p>')
        .replace(/$/, '</p>');
}

// Export Function
function exportToHTML() {
    const html = generateExportHTML();
    const blob = new Blob([html], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'Document.html';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// HTML Generation
function generateExportHTML() {
    const data = {
        title: "My Document",
        sections: [
            { id: 1, title: "Section 1", content: "Content here..." },
            { id: 2, title: "Section 2", content: "More content..." }
        ]
    };
    
    const toc = data.sections.map(s => `
        <a href="#section-${s.id}" class="toc-item">
            ${s.title}
        </a>
    `).join('');
    
    const sections = data.sections.map((s, i) => `
        <div id="section-${s.id}" class="content-section">
            <h1>${escapeHtml(s.title)}</h1>
            <div>${formatText(escapeHtml(s.content))}</div>
            <div class="section-navigation">
                <a href="#toc" class="back-to-top-link">↑ Back to Table of Contents</a>
            </div>
        </div>
    `).join('');
    
    return `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>${escapeHtml(data.title)}</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 900px; margin: 0 auto; padding: 40px; }
        .toc-item { display: block; padding: 8px 0; text-decoration: none; color: #333; }
        .toc-item:hover { background: #f0f0f0; }
        .content-section { margin: 60px 0; }
        .back-to-top-link { display: inline-block; margin-top: 40px; padding: 10px 20px; 
                           background: #f0f0f0; text-decoration: none; border-radius: 4px; }
        .floating-home { position: fixed; bottom: 30px; right: 30px; width: 50px; height: 50px;
                        background: #333; color: white; border-radius: 50%; text-align: center;
                        line-height: 50px; text-decoration: none; }
        html { scroll-behavior: smooth; }
    </style>
</head>
<body>
    <div id="toc">
        <h2>Table of Contents</h2>
        ${toc}
    </div>
    ${sections}
    <a href="#toc" class="floating-home">⌂</a>
</body>
</html>
    `;
}
```

---

## Customization Guide

### Change Colors
Update these CSS variables or direct color values:
- **Primary Text:** `#1a1a1a` (dark gray/black)
- **Secondary Text:** `#4a4a4a` (medium gray)
- **Background:** `#ffffff` (white)
- **Accent:** `#f8f9fa` (light gray for boxes)
- **Borders:** `#e0e0e0` (light gray)

### Change Font
Replace Montserrat with your preferred font:
```html
<link href="https://fonts.googleapis.com/css2?family=YourFont:wght@400;700&display=swap" rel="stylesheet">
```
```css
body { font-family: 'YourFont', sans-serif; }
```

### Adjust Layout
- **Max Width:** Change `max-width: 900px` in `.document-container`
- **Padding:** Adjust `padding: 60px 50px` in `.document-container`
- **Spacing:** Modify `margin` values in `.content-section`

### Add Custom Sections
Follow the pattern:
```javascript
${data.customSection ? `
    <div class="custom-section">
        <h2>${escapeHtml(data.customSection.title)}</h2>
        <div>${formatText(escapeHtml(data.customSection.content))}</div>
    </div>
` : ''}
```

---

## Testing Checklist

- [ ] HTML file downloads correctly
- [ ] Table of contents links work (jump to sections)
- [ ] Back-to-top links work (return to TOC)
- [ ] Floating home button works and is always visible
- [ ] Smooth scrolling works
- [ ] All content is properly escaped (no XSS vulnerabilities)
- [ ] Text formatting preserves line breaks and paragraphs
- [ ] Print preview looks good (page breaks work)
- [ ] Mobile responsive (if needed)
- [ ] No broken links or missing IDs

---

## Common Issues & Solutions

### Issue: Links don't work
**Solution:** Ensure section IDs match TOC link hrefs exactly:
- TOC: `href="#section-1"`
- Section: `id="section-1"`

### Issue: Content appears as HTML code
**Solution:** You forgot to escape HTML. Use `escapeHtml()`:
```javascript
// Wrong
<div>${userContent}</div>

// Right
<div>${escapeHtml(userContent)}</div>
```

### Issue: Line breaks don't show
**Solution:** Use `formatText()` instead of `escapeHtml()` for multi-line text:
```javascript
// Wrong
<div>${escapeHtml(multiLineText)}</div>

// Right
<div>${formatText(escapeHtml(multiLineText))}</div>
```

### Issue: Floating button doesn't appear
**Solution:** Check z-index and ensure it's not hidden by other elements:
```css
.floating-home {
    z-index: 1000; /* High enough to be on top */
    position: fixed; /* Not absolute */
}
```

---

## Advanced Features (Optional)

### 1. Progress Indicator
Add a progress bar showing reading progress:
```javascript
// Add to HTML
<div class="progress-bar">
    <div class="progress-fill" id="progress"></div>
</div>

// Add JavaScript
window.addEventListener('scroll', () => {
    const winScroll = document.body.scrollTop || document.documentElement.scrollTop;
    const height = document.documentElement.scrollHeight - document.documentElement.clientHeight;
    const scrolled = (winScroll / height) * 100;
    document.getElementById('progress').style.width = scrolled + '%';
});
```

### 2. Chapter Navigation
Add "Previous/Next" buttons between sections:
```javascript
<div class="chapter-nav">
    ${index > 0 ? `<a href="#section-${data.sections[index-1].id}" class="nav-link">← Previous</a>` : ''}
    ${index < data.sections.length - 1 ? `<a href="#section-${data.sections[index+1].id}" class="nav-link">Next →</a>` : ''}
</div>
```

### 3. Search Functionality
Add a search box (requires JavaScript in the HTML):
```html
<input type="text" id="search" placeholder="Search...">
<script>
    document.getElementById('search').addEventListener('input', (e) => {
        const searchTerm = e.target.value.toLowerCase();
        document.querySelectorAll('.content-section').forEach(section => {
            const text = section.textContent.toLowerCase();
            section.style.display = text.includes(searchTerm) ? 'block' : 'none';
        });
    });
</script>
```

---

## File Structure Recommendation

```
your-project/
├── export/
│   ├── html-export.js          # Main export functions
│   ├── html-templates.js       # HTML template builders
│   └── html-styles.js          # CSS styles
└── utils/
    └── html-helpers.js         # escapeHtml, formatText, etc.
```

---

## Summary

**Essential Components:**
1. ✅ `escapeHtml()` function (security)
2. ✅ `formatText()` function (formatting)
3. ✅ `generateExportHTML()` function (main generator)
4. ✅ `exportToHTML()` function (download trigger)
5. ✅ Table of contents with clickable links
6. ✅ Unique IDs for each section
7. ✅ Back-to-top links after each section
8. ✅ Floating home button
9. ✅ Smooth scrolling CSS
10. ✅ Print-friendly styles

**Key Principles:**
- Always escape user content
- Use semantic HTML
- Keep styles inline (standalone file)
- Test navigation thoroughly
- Make it print-friendly

---

*This guide is based on the implementation in AI Pathway V3. Adapt the patterns to fit your specific data structure and requirements.*

