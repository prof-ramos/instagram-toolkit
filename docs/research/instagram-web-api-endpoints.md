# Native Instagram Web API Endpoints

This document details the reverse-engineered Instagram Web API endpoints used during browser sessions (`www.instagram.com`). These details enable native JavaScript Chrome Extensions (content scripts or background service workers) to fetch followers/following lists with cursor pagination and execute follow/unfollow actions.

---

## 1. Required Headers for Web Requests

When executing HTTP requests from a Chrome Extension context (e.g. `fetch` in Content Script or Background Worker), the browser will automatically manage cookies if credentials are set to `include`. However, specific custom headers are required by Instagram to prevent request rejection (`403 Forbidden` / `400 Bad Request`).

| Header Name | Value / Format | Description |
| :--- | :--- | :--- |
| `X-CSRFToken` | `string` | Extracted from `document.cookie` (`csrftoken` key). Mandatory for `POST` requests. |
| `X-IG-App-ID` | `936619743392459` | Constant App ID for Instagram Web. |
| `X-ASBD-ID` | `198387` | ASBD identifier header used by Meta web apps. |
| `X-Instagram-AJAX` | `1` (or rollout hash) | Indicates an AJAX request from the web frontend. |
| `X-Requested-With` | `XMLHttpRequest` | Standard AJAX header. |
| `Content-Type` | `application/x-www-form-urlencoded` | Required for `POST` actions (follow / unfollow). |

### Extracting `csrftoken` in JS:
```javascript
function getCsrfToken() {
  const match = document.cookie.match(/csrftoken=([^;]+)/);
  return match ? match[1] : '';
}
```

---

## 2. Listing Followers & Following

There are two primary endpoint strategies available in Instagram Web: REST API `/api/v1/friendships/...` and GraphQL queries.

---

### Strategy A: REST API Endpoints (`/api/v1/friendships/...`)

#### 1. Fetch Followers
- **HTTP Method**: `GET`
- **Endpoint**: `https://www.instagram.com/api/v1/friendships/{user_id}/followers/`
- **Query Parameters**:
  - `count`: (integer, default `50`, max `100` or `200`) Number of users per page.
  - `max_id`: (string, optional) Cursor token for pagination. Omit on the first page. Pass the `next_max_id` received from the previous response.
  - `search_query`: (string, optional) Filter followers by search string.

#### 2. Fetch Following
- **HTTP Method**: `GET`
- **Endpoint**: `https://www.instagram.com/api/v1/friendships/{user_id}/following/`
- **Query Parameters**:
  - `count`: (integer, default `50`)
  - `max_id`: (string, optional) Cursor token for pagination.

#### Response JSON Structure (REST)
```json
{
  "users": [
    {
      "pk": 123456789,
      "pk_id": "123456789",
      "username": "johndoe",
      "full_name": "John Doe",
      "is_private": false,
      "profile_pic_url": "https://instagram.fcdn.net/...",
      "profile_pic_id": "3100000000000000000_123456789",
      "is_verified": false,
      "has_anonymous_profile_picture": false,
      "account_badges": [],
      "latest_reel_media": 0
    }
  ],
  "big_list": true,
  "page_size": 50,
  "next_max_id": "QVFBWE...",
  "has_more": true,
  "status": "ok"
}
```

#### Pagination Rule (REST):
- Continue fetching next pages while `has_more === true` (or `next_max_id` is present and non-empty).
- Set `max_id = response.next_max_id` in the next request parameters.

---

### Strategy B: GraphQL Endpoints (`/graphql/query/`)

- **HTTP Method**: `GET`
- **Endpoint**: `https://www.instagram.com/graphql/query/`

#### Query Hashes:
- **Followers Query Hash**: `5a2327d6db61922252a1b945d820bf3f`
- **Following Query Hash**: `d4d882b66b618245b9d30c44f779d724` (or `c76146de99bb02f6415203be841dd25a`)

#### URL Parameters:
- `query_hash`: (string) The query hash from above.
- `variables`: (URL-encoded JSON string)
  ```json
  {
    "id": "123456789",
    "include_reel": true,
    "fetch_mutual": false,
    "first": 50,
    "after": "QVFBWE..."
  }
  ```

#### Response JSON Structure (GraphQL)
```json
{
  "data": {
    "user": {
      "edge_followed_by": {
        "count": 1250,
        "page_info": {
          "has_next_page": true,
          "end_cursor": "QVFBWE..."
        },
        "edges": [
          {
            "node": {
              "id": "123456789",
              "username": "johndoe",
              "full_name": "John Doe",
              "profile_pic_url": "https://...",
              "is_verified": false,
              "is_private": false,
              "followed_by_viewer": true,
              "requested_by_viewer": false
            }
          }
        ]
      }
    }
  },
  "status": "ok"
}
```
*(Note: For following, the response path is `data.user.edge_follow`).*

---

## 3. Follow & Unfollow Actions

#### 1. Follow User Action
- **HTTP Method**: `POST`
- **Endpoint**: `https://www.instagram.com/api/v1/friendships/create/{user_id}/`
- **Headers**: Mandatory `X-CSRFToken`, `X-IG-App-ID`, `Content-Type: application/x-www-form-urlencoded`
- **Body**: `container_module=profile&nav_status=...&user_id={user_id}`

#### 2. Unfollow User Action
- **HTTP Method**: `POST`
- **Endpoint**: `https://www.instagram.com/api/v1/friendships/destroy/{user_id}/`
- **Headers**: Mandatory `X-CSRFToken`, `X-IG-App-ID`, `Content-Type: application/x-www-form-urlencoded`
- **Body**: `container_module=profile&nav_status=...&user_id={user_id}`

#### Action Response JSON Structure
```json
{
  "friendship_status": {
    "following": true,
    "followed_by": false,
    "blocking": false,
    "muting": false,
    "is_private": false,
    "incoming_request": false,
    "outgoing_request": false,
    "is_bestie": false,
    "is_restricted": false,
    "is_feed_favorite": false
  },
  "status": "ok"
}
```
*(When unfollowing, `friendship_status.following` will return `false`).*

---

## 4. Native JavaScript Chrome Extension Code Examples

### Fetch Followers (Content Script Helper)
```javascript
async function fetchFollowersPage(userId, maxId = null) {
  const csrfToken = getCsrfToken();
  const url = new URL(`https://www.instagram.com/api/v1/friendships/${userId}/followers/`);
  url.searchParams.append('count', '50');
  if (maxId) {
    url.searchParams.append('max_id', maxId);
  }

  const response = await fetch(url.toString(), {
    method: 'GET',
    headers: {
      'X-CSRFToken': csrfToken,
      'X-IG-App-ID': '936619743392459',
      'X-ASBD-ID': '198387',
      'X-Requested-With': 'XMLHttpRequest'
    },
    credentials: 'include'
  });

  if (!response.ok) {
    throw new Error(`HTTP Error ${response.status}`);
  }

  return await response.json();
}
```

### Follow / Unfollow User Helper
```javascript
async function setFollowState(userId, action = 'create') {
  // action can be 'create' (follow) or 'destroy' (unfollow)
  const csrfToken = getCsrfToken();
  const url = `https://www.instagram.com/api/v1/friendships/${action}/${userId}/`;

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      'X-CSRFToken': csrfToken,
      'X-IG-App-ID': '936619743392459',
      'X-ASBD-ID': '198387',
      'X-Requested-With': 'XMLHttpRequest'
    },
    body: new URLSearchParams({
      user_id: userId,
      container_module: 'profile'
    }).toString(),
    credentials: 'include'
  });

  if (!response.ok) {
    throw new Error(`HTTP Error ${response.status}`);
  }

  return await response.json();
}
```

---

## 5. Rate Limiting Guidelines & Best Practices for Extensions

1. **Pagination Delays**: Insert a randomized delay of 1.5s to 3.5s between consecutive page requests to mimic human scrolling and avoid hitting HTTP 429 / action blocks.
2. **Follow/Unfollow Delays**: Insert a minimum delay of 15s to 45s between follow/unfollow requests.
3. **Session Verification**: Always verify `csrftoken` presence in `document.cookie` before executing requests.
