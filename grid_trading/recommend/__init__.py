"""Auto-recommendation layer: turn real market data into grid parameters.

Public surface::

    from grid_trading.recommend import recommend_grid, GridRecommendation
"""

from grid_trading.recommend.auto_grid import (  # noqa: F401
    GridRecommendation,
    recommend_grid,
    recommend_from_bars,
)

__all__ = ["GridRecommendation", "recommend_grid", "recommend_from_bars"]
