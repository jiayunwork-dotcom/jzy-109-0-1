"""Wheatstone bridge calculation service.

Modules are split by responsibility:

* :mod:`app.divider`   -- open-circuit output as the difference of two divider ratios
* :mod:`app.thevenin`  -- Thevenin-equivalent solve with the galvanometer loaded
* :mod:`app.balance`   -- balance condition and closed-form solve for the unknown arm
* :mod:`app.registry`  -- named bridge configurations ("bridge presets")
* :mod:`app.validation`-- input validation performed before any computation
* :mod:`app.schemas`   -- HTTP request/response models
* :mod:`app.main`      -- FastAPI HTTP layer: transport and orchestration only
"""

__version__ = "1.0.0"
