import pytest
from sqlalchemy import select

from flowdeck.models import Product
from flowdeck.targets import read_targets, sync_products


def test_read_targets_skips_comments_and_duplicates(tmp_path):
    path = tmp_path / "targets.txt"
    path.write_text("# 제목\n111  # SSD\n\n222\n111\n", encoding="utf-8")

    assert read_targets(path) == ["111", "222"]


def test_read_targets_rejects_non_numeric(tmp_path):
    path = tmp_path / "targets.txt"
    path.write_text("111\nabc\n", encoding="utf-8")

    with pytest.raises(ValueError, match=":2"):
        read_targets(path)


def active_pcodes(session):
    rows = session.scalars(select(Product).where(Product.active).order_by(Product.id))
    return [p.source_product_id for p in rows]


def test_sync_adds_reactivates_and_deactivates(session_factory):
    with session_factory() as session:
        session.add_all(
            [
                Product(source="danawa", source_product_id="1", active=True),
                Product(source="danawa", source_product_id="2", active=False),
                Product(source="danawa", source_product_id="3", active=True),
            ]
        )
        session.commit()

        result = sync_products(session, "danawa", ["1", "2", "4"])

        assert (result.added, result.reactivated, result.deactivated) == (["4"], ["2"], ["3"])
        assert active_pcodes(session) == ["1", "2", "4"]
        # 빠진 상품도 행은 남는다
        assert session.scalar(select(Product).where(Product.source_product_id == "3")) is not None


def test_sync_twice_changes_nothing(session_factory):
    with session_factory() as session:
        sync_products(session, "danawa", ["1", "2"])
        result = sync_products(session, "danawa", ["1", "2"])

        assert (result.added, result.reactivated, result.deactivated) == ([], [], [])
