import collections
from collections.abc import Callable
import logging
import string
import time


class LazyRefresh:
    """
    LazyRefresh provides on‑demand, grouped attribute refreshing for classes whose
    attributes must remain up‑to‑date without refreshing on every access.

    Many data‑driven classes expose attributes whose values come from external
    sources such as SQL queries, API calls, directory listings, or other I/O.
    Refreshing these values on every attribute access is wasteful, but allowing
    them to become stale can lead to incorrect behavior. LazyRefresh solves this
    by intercepting attribute access and refreshing only when necessary.

    A subclass defines one or more *refresh groups*. Each group is created by
    calling `_register_refresh_method()` inside the subclass's `__init__`. All
    attributes assigned between calls to `_register_refresh_method()` belong to
    the same group and share:

        • a refresh method (a callable returning a dict of attribute values)
        • a refresh frequency (seconds between updates)
        • optional "stop‑when‑set" behavior

    When an attribute is accessed, LazyRefresh determines whether its group
    requires an update. If so, the refresh method is executed and the returned
    dictionary is applied to the instance. Keys in the dictionary are converted
    to PEP‑8‑compliant attribute names (e.g., "ResponseDate" → "response_date").

    Key features:
        • Grouped attribute refreshes — multiple attributes updated by one method
        • Frequency‑based refresh control (including negative values for "always")
        • Optional one‑time refresh when an attribute becomes truthy
        • Automatic mapping of external field names to PEP‑8 attribute names
        • Safe handling of concurrent refresh attempts
        • Ability to "peek" at an attribute without triggering a refresh

    Example:
        class Heartbeat(LazyRefresh):
            def __init__(self):
                super().__init__()

                self.response_date = None
                self.alerts = []
                self._register_refresh_method(self._load_status)

                self.server_name = ""
                self._register_refresh_method(self._load_server_info)

            def _load_status(self):
                return {
                    "ResponseDate": query_response_date(),
                    "Alerts": query_alerts(),
                }

            def _load_server_info(self):
                return {
                    "ServerName": query_server_name(),
                }

    In this example, accessing `response_date` or `alerts` triggers `_load_status`
    when needed, while accessing `server_name` triggers `_load_server_info`.

    Subclasses should:
        • assign attributes in __init__
        • call `_register_refresh_method()` after each group of assignments
        • implement refresh methods that return dictionaries of new values

    LazyRefresh is designed for near‑real‑time data access without unnecessary
    refresh calls, reducing load while ensuring correctness.
    """
    _subclass_list = []

    def __init__(self):
        self._updated_attributes = set()
        self._data_methods = {}  # attribute_name: method
        self._update_frequency = {}  # method: update_frequency
        self._next_update = {}  # method: next_update
        self._map_fields = {}  # {key_name: dictionary name}
        self._stop_when_set = []
        self._update_in_progress = collections.defaultdict(lambda: False)
        self._skip_fields = []  # Ignore these columns that might be in the results dictionary from the query

        self._report_missing_attributes = True

        self._log = logging.getLogger(self.__class__.__name__)

    def peek(self, name):
        """ Call to get the attribute's value without refreshing """
        return self.__getattribute__(name, True)

    def __setattr__(self, key, value):
        """ Attribute setting logic """
        if not key.startswith('_'):
            if key not in self.__dict__ and key in self._map_fields:
                key = self._map_fields[key]

            if key not in self._updated_attributes:
                try:
                    if value != super().__getattribute__(key):
                        self._updated_attributes.add(key)
                except AttributeError:
                    pass

        super().__setattr__(key, value)

    def __getattribute__(self, name, skip_refresh: bool = False):
        """ Intercept attribute access and refresh if applicable """

        # WARNING: Be careful adding logic here. Any attribute access inside this method
        # can trigger recursion. Always use super().__getattribute__ for lookups.
        if not name.startswith('_'):
            if name not in self.__dict__ and name in self._map_fields:
                name = self._map_fields[name]

            if not skip_refresh and name in self._data_methods:
                if name not in self._stop_when_set or name not in self._updated_attributes:
                    method = self._data_methods[name]
                    next_update = self._next_update[method]

                    if next_update and time.time() >= next_update and not self._update_in_progress[method]:
                        update_frequency = self._update_frequency[method]

                        try:
                            self._update_in_progress[method] = True
                            results = method()
                        except Exception:
                            raise
                        finally:
                            self._update_in_progress[method] = False

                        if update_frequency:
                            self._next_update[method] = time.time() + update_frequency
                        else:
                            self._next_update[method] = 0  # Prevent future updates

                        if results:  # Allow for methods that update directly
                            self._update_attribute_values(results, method.__name__)

        return super().__getattribute__(name)

    def _is_new_word(self, character, this_word, attribute_name, index):
        is_new = False
        if not this_word:
            is_new = False
        else:
            last_character = this_word[-1]
            if character.isupper() and last_character.isupper():
                # Two sequential upper case character.
                # Only start a new word if the next character is not another upper case
                try:
                    next_character = attribute_name[index + 1]
                    if next_character.isalpha() and not next_character.isupper():
                        # The next character is not upper, so start a new word
                        is_new = True
                except IndexError:
                    # End of the attribute, ignore the error
                    pass
            elif character.isupper() and last_character.islower():
                is_new = True
            elif character.isnumeric() and last_character.isalpha():
                # A number after an alpha is a new word
                is_new = True
            elif character.isalpha() and last_character.isnumeric():
                # Alpha after number is a new word
                is_new = True

        return is_new

    def _pep8_attribute_name(self, attribute_name) -> str:
        """ Takes an attribute name and changes it to a PEP8-compliant attribute name (lowercase with underscores)

        :param attribute_name: Original attribute name
        :return: PEP-8 compliant attribute name
        """
        pep_8_name = ''
        this_word = ''
        valid_characters = set(string.ascii_letters + '0123456789')

        attribute_name = str(attribute_name)  # Force a string
        if not attribute_name:
            attribute_name = 'null'

        for index, character in enumerate(attribute_name):
            if character not in valid_characters:
                character = '_'

            if character == '_':
                pep_8_name += this_word.lower()
                this_word = ''

                if not pep_8_name.endswith('_'):
                    pep_8_name += '_'
            else:
                if self._is_new_word(character, this_word, attribute_name, index):
                    # Start of a new word
                    pep_8_name += this_word.lower() + '_'
                    this_word = ''

                this_word += character

        # If a word was being built, add it
        pep_8_name += this_word.lower()

        # Get rid of leading and trailing underscores
        pep_8_name = pep_8_name.strip('_')
        if pep_8_name[:1].isdigit():
            pep_8_name = 'number_{}'.format(pep_8_name)

        return pep_8_name

    def _update_attribute_values(self, results, method_name):
        """ Apply refresh results """
        missing_attributes = []

        # Go through the results and set each instance attribute to the proper value
        for field, value in results.items():
            if field not in self._skip_fields:
                pep8_key = self._map_fields.get(field, self._pep8_attribute_name(field))
                if pep8_key not in self.__dict__:
                    # This key doesn't have a matching instance attribute, so add it to the list
                    missing_attributes.append(f'{field}: {pep8_key}, method {method_name}')

                try:
                    setattr(self, pep8_key, value)
                except AttributeError:
                    print(pep8_key, value)

        if self._is_new_subclass():
            # Warn of any inconsistencies
            if self._report_missing_attributes and missing_attributes:
                self._log.warning('The following keys from method {} do not have attributes in {} (database column: '
                                  'expected attribute name):\n    {}'.format(method_name,
                                                                             self._get_subclass_name(),
                                                                             '\n    '.join(missing_attributes)))

    def _register_refresh_method(self,
                                 refresh_method: Callable,
                                 refresh_frequency: int = 30,
                                 refresh_immediately: bool = True,
                                 stop_when_set: bool = False):
        """ When calling _register_refresh_method, all attributes assigned prior to the call in the
            subclass's __init__ are placed into a refresh group that uses the provided refresh_method
            to update their values. Each call creates a new refresh group containing only the attributes
            assigned after the previous call. This allows grouping attributes that can all be refreshed
            with a single method.

        :param refresh_method: A callable that is executed whenever any of the attributes in this refresh
            group is accessed.
        :param refresh_frequency: Minimum number of seconds to wait between refreshes. Set to 0 to refresh
            only on the first access. Set to a negative number to have it update every time, with no delay.
            If using a negative value, be aware of any additional server load or delays this may cause.
        :param refresh_immediately: If False, the first refresh will not occur until the refresh_frequency
            interval has passed.
        :param stop_when_set: If True, stop refreshing once the attribute has a truthy value. This differs from
            refresh_frequency=0,which stops refreshing even if the value is falsy (empty, 0, False, etc.).
        """
        for this_attribute in self.__dict__:
            if not this_attribute.startswith('_') and this_attribute not in self._data_methods:
                self._data_methods[this_attribute] = refresh_method
                self._update_frequency[refresh_method] = refresh_frequency

                if refresh_immediately:
                    self._next_update[refresh_method] = time.time()
                else:
                    self._next_update[refresh_method] = time.time() + refresh_frequency

                if stop_when_set:
                    self._stop_when_set.append(this_attribute)

                try:
                    # Remove it from updated since it was only set during instantiation
                    self._updated_attributes.remove(this_attribute)
                except KeyError:
                    pass

    @classmethod
    def _get_subclass_name(cls):
        return cls.__name__

    @classmethod
    def _is_new_subclass(cls):
        if cls not in cls._subclass_list:
            is_new = True
            cls._subclass_list.append(cls)
        else:
            is_new = False

        return is_new

    def update(self):
        """ Set the timer to allow all methods to update. Will not reset static methods (with update frequency of 0) """
        for this_method, next_update in self._next_update.items():
            if next_update:
                self._next_update[this_method] = time.time()


if __name__ == '__main__':
    class LazyTest(LazyRefresh):
        def __init__(self):
            super().__init__()

            self.first_attribute = ''
            self.second_attribute = False
            self._register_refresh_method(self.test_method, refresh_frequency=-1, stop_when_set=True)

        def test_method(self):
            print('calling refresh method')
            if self.peek('second_attribute') is True:
                result = False
            else:
                result = True
            return {'second_attribute': result}


    test = LazyTest()

    print(test.first_attribute, test.second_attribute)
    print(test.first_attribute, test.second_attribute)
    test.first_attribute = '123'
    print(test.first_attribute, test.second_attribute)
