from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin
from app.errors import app_error
from app.http import ok
from app.models import Centre, CentreTest, DiagnosticTest
from app.schemas import CentreCreate, CentreOut, CentreTestCreate, CentreTestOut, TestCreate, TestOut
from app.util import to_paise

router = APIRouter(tags=["centres"])
admin_router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/centres")
def list_centres(db: Session = Depends(get_db)):
    centres = db.scalars(select(Centre).order_by(Centre.id)).all()
    items = [CentreOut.model_validate(c) for c in centres]
    return ok({"items": items, "total": len(items)})


@router.get("/centres/{centre_id}")
def get_centre(centre_id: int, db: Session = Depends(get_db)):
    centre = db.get(Centre, centre_id)
    if centre is None:
        raise app_error("CENTRE_NOT_FOUND", f"Centre {centre_id} does not exist")
    return ok(CentreOut.model_validate(centre))


@router.get("/tests")
def list_tests(db: Session = Depends(get_db)):
    tests = db.scalars(select(DiagnosticTest).order_by(DiagnosticTest.id)).all()
    items = [TestOut.model_validate(t) for t in tests]
    return ok({"items": items, "total": len(items)})


@admin_router.post("/centres")
def create_centre(body: CentreCreate, db: Session = Depends(get_db)):
    centre = Centre(name=body.name.strip(), location=body.location.strip())
    db.add(centre)
    db.commit()
    return ok(CentreOut.model_validate(centre), 201)


@admin_router.post("/tests")
def create_test(body: TestCreate, db: Session = Depends(get_db)):
    test = DiagnosticTest(name=body.name.strip(), description=body.description)
    db.add(test)
    db.commit()
    return ok(TestOut.model_validate(test), 201)


@admin_router.post("/centres/{centre_id}/tests")
def add_test_to_centre(centre_id: int, body: CentreTestCreate, db: Session = Depends(get_db)):
    centre = db.get(Centre, centre_id)
    if centre is None:
        raise app_error("CENTRE_NOT_FOUND", f"Centre {centre_id} does not exist")
    test = db.get(DiagnosticTest, body.test_id)
    if test is None:
        raise app_error("TEST_NOT_FOUND", f"Test {body.test_id} does not exist")
    existing = db.scalar(
        select(CentreTest).where(CentreTest.centre_id == centre_id, CentreTest.test_id == body.test_id)
    )
    if existing is not None:
        raise app_error(
            "TEST_ALREADY_OFFERED",
            f"Centre {centre_id} already offers test {body.test_id}",
        )
    centre_test = CentreTest(centre_id=centre_id, test_id=body.test_id, price_paise=to_paise(body.price))
    db.add(centre_test)
    db.commit()
    return ok(CentreTestOut.model_validate(centre_test), 201)
