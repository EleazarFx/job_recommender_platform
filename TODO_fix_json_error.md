# Fix JSON Parse Error: Unexpected token '<'

## Problem
JavaScript fetch() calls expect JSON but receive HTML, causing:
`SyntaxError: Unexpected token '<', "<!DOCTYPE "... is not valid JSON`

## Root Causes
1. `saved_jobs()` view always returns HTML, never JSON for count_only/AJAX requests
2. `base.html` calls non-existent `/jobs/saved/count/` endpoint

## Steps
- [x] Step 1: Update `saved_jobs()` view in `apps/jobs/views.py` to return JsonResponse for AJAX/count_only
- [x] Step 2: Fix fetch URL in `templates/base/base.html` to use correct endpoint with count_only=1
- [x] Step 3: Verify fix by checking no more HTML responses for JSON requests

## Changes Made
- `apps/jobs/views.py`: Added early JSON response in `saved_jobs()` when `X-Requested-With: XMLHttpRequest` or `count_only=1` is present
- `templates/base/base.html`: Changed `fetch('/jobs/saved/count/')` to `fetch('{% url "jobs:saved" %}?count_only=1')` with proper AJAX header

