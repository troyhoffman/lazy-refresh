# LazyRefresh  
A lightweight Python utility that automatically refreshes object attributes on access using a grouped ReactiveModel pattern. Ideal for API clients, distributed systems, dashboards, polling loops, and automation frameworks that need near‑real‑time data without boilerplate `@property` methods. 

LazyRefresh provides reactive, grouped attribute updates without the overhead of observer frameworks or repetitive `@property` methods.

---

## Features
- **Automatic refresh on attribute access**  
- **Grouped refresh operations** (one call updates many attributes)  
- **Configurable refresh frequency**  
- **Truthiness‑based stop behavior** (stop refreshing once a flag becomes meaningful)  
- **PEP8 key normalization** (dictionary keys → Pythonic attribute names)  
- **No boilerplate properties**  
- **Zero external dependencies**

---

## Installation
```bash
pip install lazyrefresh
```

## Example

```python
from lazyrefresh import LazyRefresh

class MyLazyClass(LazyRefresh):
    def __init__(self):
        self.last_updated = None
        self.next_update = None
        self._register_refresh_method(self.api_refresh)

        self.text_file_contents = ""
        self._filename = "testfile.txt"
        self._register_refresh_method(self.read_file, refresh_frequency=0)

        self.is_complete = False
        self._register_refresh_method(self.check_status, refresh_frequency=30, stop_when_set=True)

    def api_refresh(self):
        return {
            "last_updated": "2026-08-18T08:00:00",
            "next_update": "2026-08-18T08:10:00"
        }

    def read_file(self):
        with open(self._filename) as f:
            return {"text_file_contents": f.read()}

    def check_status(self):
        return {"is_complete": True}
```

## How It Works

LazyRefresh intercepts `__getattribute__()` and determines whether an attribute should be refreshed based on:
- **the last update time**
- **the refresh frequency**
- **whether the attribute has been accessed before**
- **optional truthiness‑based stop rules**

Attributes beginning with `_` are never refreshed.
Each call to `_register_refresh_method()` creates a refresh group containing all attributes defined since the previous registration.

## Refresh Methods

A refresh method:
- **takes no parameters**
- **returns a dict mapping attribute names → values**
- **may pull from any source: APIs, SQL, files, sockets, message buses, etc.**
- **may return keys in any naming style — they are normalized to PEP8 automatically**

---

Example:
```python
def api_refresh(self):
    return {
        "ResponseDate": "2026-08-18",
        "UserCount": 42
    }
```
Becomes:
```python
self.response_date
self.user_count
```

## Example Behavior

Group 1: `last_updated`, `next_update`
Refreshes every 10 seconds (default).

Group 2: `text_file_contents`
Refreshes only once because `refresh_frequency`=0.

Group 3: `is_complete`
Refreshes until the value becomes truthy, then stops permanently.

Ungrouped: `database_server`
Never refreshes because it was defined after the last registration.

## Use Cases

LazyRefresh is ideal for:
- **API clients with cached responses**
- **distributed system polling**
- **file/directory monitors**
- **real‑time dashboards**
- **background workers**
- **automation frameworks needing reactive data models**

It centralizes refresh logic and eliminates repetitive `@property` code.

## License

MIT License. See the LICENSE file for details