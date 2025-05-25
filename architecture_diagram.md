# AI Expert Panel - System Architecture

## High-Level Architecture Flow

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│                 │    │                 │    │                 │
│   USER INPUT    │───▶│  FLASK BACKEND  │───▶│   VENICE AI     │
│                 │    │                 │    │                 │
│ • Business      │    │ • API Wrapper   │    │ • qwen-2.5-     │
│   Problem       │    │ • CORS Handler  │    │   qwq-32b       │
│ • Web Interface │    │ • Data Process  │    │ • Chat API      │
│                 │    │ • Error Handle  │    │ • JSON Schema   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│                 │    │                 │    │                 │
│  FRONTEND UI    │◀───│  DATA PIPELINE  │◀───│  AI PROCESSING  │
│                 │    │                 │    │                 │
│ • Modern React- │    │ • Text Cleaning │    │ • Persona Gen   │
│   like Interface│    │ • JSON Parsing  │    │ • Expert Analysis│
│ • Progress Bars │    │ • Response      │    │ • Synthesis     │
│ • PDF Export    │    │   Formatting    │    │ • Insights      │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Detailed Component Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND LAYER                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │   INPUT     │  │ NAVIGATION  │  │  PROGRESS   │  │    PDF      │       │
│  │  SECTION    │  │    PANEL    │  │  TRACKING   │  │  GENERATOR  │       │
│  │             │  │             │  │             │  │             │       │
│  │ • Textarea  │  │ • Expert    │  │ • Spinner   │  │ • jsPDF     │       │
│  │ • Submit    │  │   List      │  │ • Progress  │  │ • Format    │       │
│  │ • Validation│  │ • Active    │  │   Bar       │  │ • Download  │       │
│  │             │  │   States    │  │ • Status    │  │             │       │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ HTTP POST
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           BACKEND LAYER                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    FLASK APPLICATION                                │   │
│  │                                                                     │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │   │
│  │  │   ROUTES    │  │    CORS     │  │   ERROR     │                │   │
│  │  │             │  │  HANDLER    │  │  HANDLER    │                │   │
│  │  │ • /health   │  │             │  │             │                │   │
│  │  │ • /process_ │  │ • Origins   │  │ • Try/Catch │                │   │
│  │  │   problem   │  │ • Headers   │  │ • Logging   │                │   │
│  │  │ • /test     │  │ • Methods   │  │ • Fallback  │                │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    VENICE API INTEGRATION                          │   │
│  │                                                                     │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │   │
│  │  │ API WRAPPER │  │   SCHEMA    │  │    TEXT     │                │   │
│  │  │             │  │ VALIDATION  │  │  CLEANING   │                │   │
│  │  │ • call_     │  │             │  │             │                │   │
│  │  │   venice_   │  │ • JSON      │  │ • Remove    │                │   │
│  │  │   api()     │  │   Schema    │  │   [REF]     │                │   │
│  │  │ • Headers   │  │ • Response  │  │ • Format    │                │   │
│  │  │ • Timeout   │  │   Format    │  │   Text      │                │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ HTTPS API Calls
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           VENICE AI LAYER                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    VENICE AI API                                    │   │
│  │                                                                     │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │   │
│  │  │   MODEL     │  │  ENDPOINT   │  │  RESPONSE   │                │   │
│  │  │             │  │             │  │             │                │   │
│  │  │ • qwen-2.5- │  │ • /v1/chat/ │  │ • JSON      │                │   │
│  │  │   qwq-32b   │  │   completions│  │   Format    │                │   │
│  │  │ • 120s      │  │ • Bearer    │  │ • Structured│                │   │
│  │  │   Timeout   │  │   Auth      │  │   Output    │                │   │
│  │  │ • Temp 0.7  │  │ • HTTPS     │  │ • Private   │                │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow Sequence

```
USER                FRONTEND            BACKEND             VENICE AI
 │                     │                   │                    │
 │ 1. Enter Problem    │                   │                    │
 ├────────────────────▶│                   │                    │
 │                     │ 2. POST Request   │                    │
 │                     ├──────────────────▶│                    │
 │                     │                   │ 3. Generate        │
 │                     │                   │    Personas        │
 │                     │                   ├───────────────────▶│
 │                     │                   │ 4. Persona Data    │
 │                     │                   │◀───────────────────┤
 │                     │                   │ 5. Get Insights    │
 │                     │                   │    (10x calls)     │
 │                     │                   ├───────────────────▶│
 │                     │                   │ 6. Expert Analysis │
 │                     │                   │◀───────────────────┤
 │                     │                   │ 7. Synthesis       │
 │                     │                   ├───────────────────▶│
 │                     │                   │ 8. Final Report    │
 │                     │                   │◀───────────────────┤
 │                     │ 9. Complete Data  │                    │
 │                     │◀──────────────────┤                    │
 │ 10. Display Results │                   │                    │
 │◀────────────────────┤                   │                    │
 │ 11. Download PDF    │                   │                    │
 ├────────────────────▶│                   │                    │
```

## Technology Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                        TECHNOLOGY STACK                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  FRONTEND                    BACKEND                   AI       │
│  ┌─────────────┐            ┌─────────────┐         ┌─────────┐ │
│  │ HTML5       │            │ Python 3.x  │         │ Venice  │ │
│  │ CSS3        │            │ Flask       │         │ AI API  │ │
│  │ JavaScript  │            │ Flask-CORS  │         │ qwen-   │ │
│  │ jsPDF       │            │ Requests    │         │ 2.5-    │ │
│  │ Inter Font  │            │ JSON        │         │ qwq-32b │ │
│  │ Font Awesome│            │ Gunicorn    │         │         │ │
│  └─────────────┘            └─────────────┘         └─────────┘ │
│                                                                 │
│  DEPLOYMENT                  SECURITY                          │
│  ┌─────────────┐            ┌─────────────┐                   │
│  │ Local Dev   │            │ CORS        │                   │
│  │ Render.com  │            │ HTTPS       │                   │
│  │ Netlify     │            │ API Keys    │                   │
│  │ Firebase    │            │ Private     │                   │
│  │             │            │ Processing  │                   │
│  └─────────────┘            └─────────────┘                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Key Features Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FEATURE MAP                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  INPUT PROCESSING           EXPERT GENERATION                  │
│  ┌─────────────┐            ┌─────────────┐                   │
│  │ • Text      │            │ • 10 Unique │                   │
│  │   Validation│            │   Personas  │                   │
│  │ • Problem   │            │ • Specialized│                   │
│  │   Analysis  │            │   Expertise │                   │
│  │ • Sanitize  │            │ • Focus     │                   │
│  │   Input     │            │   Areas     │                   │
│  └─────────────┘            └─────────────┘                   │
│                                                                 │
│  INSIGHT ANALYSIS           SYNTHESIS ENGINE                   │
│  ┌─────────────┐            ┌─────────────┐                   │
│  │ • Individual│            │ • Executive │                   │
│  │   Expert    │            │   Summary   │                   │
│  │   Analysis  │            │ • Key       │                   │
│  │ • Confidence│            │   Themes    │                   │
│  │   Levels    │            │ • Blind     │                   │
│  │ • Risk/Opp  │            │   Spots     │                   │
│  │   Assessment│            │ • Action    │                   │
│  │             │            │   Plan      │                   │
│  └─────────────┘            └─────────────┘                   │
│                                                                 │
│  UI/UX FEATURES             OUTPUT GENERATION                  │
│  ┌─────────────┐            ┌─────────────┐                   │
│  │ • Modern    │            │ • Clean PDF │                   │
│  │   Design    │            │ • Structured│                   │
│  │ • Responsive│            │   Report    │                   │
│  │ • Progress  │            │ • Executive │                   │
│  │   Tracking  │            │   Ready     │                   │
│  │ • Animations│            │ • Download  │                   │
│  └─────────────┘            └─────────────┘                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
``` 