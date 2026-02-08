import sys
import os
from datetime import datetime

# Add the project root to sys.path
sys.path.append(os.getcwd())

try:
    from app.database.schemas.user import UserBase, UserRole
    from app.database.schemas.bus import Bus
    from app.database.schemas.student import StudentBase
    from app.database.schemas.student_bus_assignment import StudentBusAssignment
    from app.database.schemas.parent_student_relation import ParentStudentRelation

    print("Successfully imported schemas.")

    # 1. Test Bus Schema with Driver
    driver = UserBase(
        full_name="Test Driver",
        email="driver@test.com",
        phone_number="5551234567",
        role=UserRole.sofor
    )
    
    bus = Bus(
        id="bus1",
        plate_number="34 ABC 12",
        capacity=20,
        school_id="school1",
        current_driver_id="driver1",
        current_driver=driver
    )
    
    print("\n--- Bus Serialization Test ---")
    print(bus.model_dump_json(indent=2))
    
    if bus.current_driver and bus.current_driver.full_name == "Test Driver":
        print("✅ Bus.current_driver serialized correctly.")
    else:
        print("❌ Bus.current_driver FAILED.")

    # 2. Test StudentBusAssignment Schema
    student = StudentBase(
        full_name="Ali Yilmaz",
        student_number="101",
        school_id="school1"
    )
    
    assignment = StudentBusAssignment(
        id="assign1",
        bus_id="bus1",
        student_id="student1",
        bus=bus,
        student=student
    )
    
    print("\n--- Assignment Serialization Test ---")
    print(assignment.model_dump_json(indent=2))
    
    if assignment.student and assignment.student.full_name == "Ali Yilmaz":
        print("✅ Assignment.student serialized correctly.")
    else:
        print("❌ Assignment.student FAILED.")

    # 3. Test ParentStudentRelation Schema
    from app.database.schemas.user import UserBase
    parent = UserBase(
        full_name="Ayse Yilmaz",
        email="parent@test.com",
        phone_number="5551234568",
        role=UserRole.veli
    )

    relation = ParentStudentRelation(
        id="rel1",
        student_id="student1",
        parent_id="parent1",
        student=student,
        parent=parent
    )

    print("\n--- ParentRelation Serialization Test ---")
    print(relation.model_dump_json(indent=2))

    if relation.parent and relation.parent.full_name == "Ayse Yilmaz":
        print("✅ ParentRelation.parent serialized correctly.")
    else:
        print("❌ ParentRelation.parent FAILED.")

except ImportError as e:
    print(f"❌ ImportError: {e}")
except Exception as e:
    print(f"❌ Unexpected Error: {e}")
