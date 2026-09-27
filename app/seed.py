from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import Centre, CentreTest, DiagnosticTest, User
from app.security import hash_password
from app.util import to_paise

TESTS = [
    ("CBC", "Complete Blood Count"),
    ("Thyroid Profile", "T3, T4 and TSH levels"),
    ("Lipid Profile", "Cholesterol and triglycerides"),
    ("Blood Glucose", "Fasting blood sugar"),
    ("Liver Function Test", "Liver enzymes panel"),
]

CENTRES = [
    ("EVE Diagnostics Delhi", "Delhi", {"CBC": 500, "Thyroid Profile": 700, "Lipid Profile": 900}),
    ("EVE Diagnostics Noida", "Noida", {"CBC": 450, "Thyroid Profile": 650, "Blood Glucose": 300}),
]

def make_admin(db, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, full_name="Admin", password_hash=hash_password(password), is_admin=True)
        db.add(user)
        db.commit()
    return user


def run_seed() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        from app.config import settings

        make_admin(db, settings.seed_admin_email, settings.seed_admin_password)

        tests = {}
        for name, description in TESTS:
            test = db.scalar(select(DiagnosticTest).where(DiagnosticTest.name == name))
            if test is None:
                test = DiagnosticTest(name=name, description=description)
                db.add(test)
                db.commit()
            tests[name] = test

        for centre_name, location, offerings in CENTRES:
            centre = db.scalar(select(Centre).where(Centre.name == centre_name))
            if centre is None:
                centre = Centre(name=centre_name, location=location)
                db.add(centre)
                db.commit()
            for test_name, price in offerings.items():
                test = tests[test_name]
                exists = db.scalar(
                    select(CentreTest).where(
                        CentreTest.centre_id == centre.id, CentreTest.test_id == test.id
                    )
                )
                if exists is None:
                    db.add(CentreTest(centre_id=centre.id, test_id=test.id, price_paise=to_paise(price)))
        db.commit()
        print("Seed complete: admin + centres + tests created")


if __name__ == "__main__":
    run_seed()
