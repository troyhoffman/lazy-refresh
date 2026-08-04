# lazy-refresh
A lightweight Python utility that lazily refreshes object data on attribute access using the ReactiveModel pattern.

There are many situations in Python where an attribute needs to be refreshed in near-real time—querying a database, calling an API, updating a SignalR client, or reading a file. Traditionally, this is handled with @property methods that fetch new data, update an internal attribute, and return the value. This works for a few properties, but it does not scale well when dozens of attributes need refreshing. It also requires boilerplate code to manage refresh timing, prevent excessive calls, and avoid redundant refreshes for data that is static but initially loaded from an external source.

LazyRefresh solves this by using a ReactiveModel pattern to automatically update attributes on access without relying on properties. It intercepts calls to `__getattribute__` and conditionally executes a refresh method based on the last update time and whether the attribute has been accessed before.

## How to Use

Inherit from LazyRefresh and define attributes normally. Attributes beginning with a leading underscore are excluded from lazy refresh behavior.

Group attributes by the refresh operation required. For example, if an API call returns values for 25 attributes, define those attributes and then call `_register_refresh_method` to create a refresh group. Each call to `_register_refresh_method` creates a new group containing only the attributes defined since the previous call.

The default refresh frequency is once every 10 seconds. If an attribute is accessed before the refresh interval has passed, the previous value is returned without calling the refresh method.

## Refresh Methods

A refresh method is defined in your class. It:

- takes no parameters
- returns a dictionary mapping attribute names to values

This dictionary can be populated using any data source: SQL queries, API calls, SignalR messages, file reads, directory listings, etc.

Dictionary keys are automatically converted to PEP8-compliant attribute names. For example, a database column named ResponseDate will map to an attribute named response_date.

## Example

```python
class MyLazyClass(LazyRefresh):
    def __init__(self, db_server: str):
        self.last_updated = None
        self.next_update = None
        self._register_refresh_method(api_refresh_method)

        self.text_file_contents = ''
        self._filename = 'testfile.txt'
        self._register_refresh_method(read_text_contents, refresh_frequency=0)

        self.is_complete = False
        self._register_refresh_method(query_update_date, refresh_frequency=30, stop_when_set=True)

        self.database_server = db_server
```

### Example Behavior

**Group 1: last_updated, next_update**
Accessing either attribute triggers `api_refresh_method` if at least 10 seconds have passed since the last refresh. The method returns a dictionary containing updated values for both attributes.

**Group 2: text_file_contents**
On first access, `read_text_contents` is called to read the file and return a dictionary containing text_file_contents.  
Accessing _filename does not trigger a refresh because it begins with an underscore. This allows grouping internal attributes with the refresh group without triggering unnecessary refreshes.
Because refresh_frequency=0, subsequent accesses do not refresh the file contents—even if the file is empty. This avoids unnecessary file reads when the value is static.

**Group 3: is_complete**  
Accessing is_complete triggers `query_update_date` if at least 30 seconds have passed.  
If the returned value is falsy, future accesses continue refreshing.  
Once the value becomes truthy, future refreshes stop.  
This is useful for flags that indicate completion of a process, since once complete, the value will not revert.

**Ungrouped: database_server**
Accessing database_server does not trigger a refresh because there is no call to ``_register_refresh_method`` after it. This allows exposing attributes that do not refresh.

---

## Key Features

- **Automatic refresh on access** — attributes update themselves when read, based on timing and logic rules.  
- **Grouped refreshes** — multiple attributes can share a single refresh method for efficiency.  
- **Flexible refresh frequency** — control how often each group updates.  
- **Truthiness-based stop behavior** — optionally stop refreshing once a value becomes meaningful.  
- **PEP8 key normalization** — automatically converts dictionary keys to Pythonic attribute names.  
- **No boilerplate properties** — eliminates repetitive `@property` code for dynamic data.

---

## Why LazyRefresh?

LazyRefresh is ideal for applications that need lightweight, reactive data models without the overhead of full observer frameworks. It’s especially useful for:

- API clients that cache responses  
- database models that lazily hydrate data  
- file or directory monitors  
- real-time dashboards  
- background polling systems
- test automation frameworks

By centralizing refresh logic, it keeps your code clean, efficient, and easy to maintain.

---

## License

This project is licensed under the **MIT License** — see the LICENSE file for details.
