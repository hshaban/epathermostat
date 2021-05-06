<<<<<<< HEAD:thermostat/__init__.py
VERSION = (1, 7, 2)
=======
VERSION = "2.0.0nw1"

>>>>>>> 477b3fd6dc61915b576a3706d7d429d8a1c8f414:thermostat_nw/__init__.py

def get_version():
    return VERSION


# This try/except clause is a hack to make the get_version method work for the
# initial setup, which will fail with an ImportError because pandas hasn't yet
# been installed. Post-setup, this provides an import shortcut to Thermostat.
try:
    from .core import Thermostat  # noqa: F401
except ImportError:
    pass
