"""restore fast shipping delivery fees

#33: 빠른배송 판매처의 배송비 칸 안내 문구("낮 3시 이전 주문 시…")의 숫자가 배송비 앞에 붙어
저장됐다 (3,000원 → 33,000원). 앞의 시각 숫자를 떼어 원래 배송비로 되돌린다.

규칙: 1만 원 이상인 다나와 배송비에서 앞 1~2자리를 떼었을 때, 뗀 숫자가 1~12(시각)이고 남은 값이
다나와에서 실제로 쓰인 1만 원 미만 배송비면 그 값으로 바꾼다. 하나라도 규칙으로 설명되지 않으면
아무것도 바꾸지 않고 멈춘다. 2026-11-01 기준 11가지 값(5,050행)이 모두 규칙에 맞았다.

추론으로 복원한 값이다. 바꾼 행 수와 값 대응은 audit_log에 남긴다.

Revision ID: 3de82cbb3d79
Revises: f0769489b0f3
Create Date: 2026-11-01 22:51:15.443010

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3de82cbb3d79"
down_revision: str | Sequence[str] | None = "f0769489b0f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DANAWA_FEES = """
    select distinct sp.delivery_fee
    from seller_prices sp
    join price_snapshots s on s.id = sp.snapshot_id
    join products p on p.id = s.product_id
    where p.source = 'danawa' and {condition}
"""


def restore(value: int, normal: set[int]) -> int | None:
    text = str(value)
    for cut in (1, 2):
        hour, rest = int(text[:cut]), int(text[cut:])
        if 1 <= hour <= 12 and rest in normal:
            return rest
    return None


def upgrade() -> None:
    conn = op.get_bind()
    normal = set(
        conn.execute(
            sa.text(DANAWA_FEES.format(condition="sp.delivery_fee > 0 and sp.delivery_fee < 10000"))
        ).scalars()
    )
    wrong = conn.execute(
        sa.text(DANAWA_FEES.format(condition="sp.delivery_fee >= 10000"))
    ).scalars()

    mapping = {}
    for value in sorted(wrong):
        fixed = restore(value, normal)
        if fixed is None:
            raise RuntimeError(f"규칙으로 설명되지 않는 다나와 배송비가 있어 멈춤: {value}")
        mapping[value] = fixed

    total = 0
    for old, new in mapping.items():
        result = conn.execute(
            sa.text(
                """
                update seller_prices sp set delivery_fee = :new
                from price_snapshots s join products p on p.id = s.product_id
                where s.id = sp.snapshot_id and p.source = 'danawa' and sp.delivery_fee = :old
                """
            ),
            {"old": old, "new": new},
        )
        total += result.rowcount

    if total:
        detail = f"#33 빠른배송 안내 숫자가 붙은 배송비 {total}행 복원. " + ", ".join(
            f"{old}→{new}" for old, new in mapping.items()
        )
        conn.execute(
            sa.text(
                "insert into audit_log (at, actor, action, target, detail) "
                "values (now(), 'migration', 'data_fixed', 'seller_prices.delivery_fee', :detail)"
            ),
            {"detail": detail},
        )
    print(f"배송비 복원: {total}행 {mapping}")


def downgrade() -> None:
    # 원래 잘못된 값(앞에 붙은 시각 숫자)은 남기지 않아서 되돌리지 않는다
    pass
