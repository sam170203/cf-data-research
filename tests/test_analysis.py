"""Tests for analysis layer."""


def test_analysis_imports():
    from analysis.queries import (
        get_average_problems_before_rating,
        get_fastest_growth_users,
        get_tag_distribution_by_rating_bucket,
        get_users_reaching_rating,
    )
    assert callable(get_users_reaching_rating)
    assert callable(get_average_problems_before_rating)
    assert callable(get_tag_distribution_by_rating_bucket)
    assert callable(get_fastest_growth_users)
