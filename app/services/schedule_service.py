from datetime import datetime, timedelta, timezone
from app.models.models import DoctorSchedule, Appointment
from app import db
import logging

logger = logging.getLogger(__name__)

def generate_doctor_schedules(
    doctor_id,
    start_date=None,
    days=7,
    start_hour=9,
    end_hour=17,
    slot_duration=30,
    skip_weekends=False,
    delete_existing=False
):
    """
    Generate doctor schedule slots.
    
    :param doctor_id: ID of the doctor
    :param start_date: Starting date for the schedule (datetime)
    :param days: Number of days to generate slots for
    :param start_hour: Starting hour of the workday (0-23)
    :param end_hour: Ending hour of the workday (1-24)
    :param slot_duration: Duration of each slot in minutes
    :param skip_weekends: Skip weekend days (Saturday and Sunday)
    :param delete_existing: Delete existing schedules in the period
    """
    if start_date is None:
        start_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    if start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=timezone.utc)
    
    if delete_existing:
        appointments = Appointment.query.filter(
            Appointment.doctor_id == doctor_id,
            Appointment.status == 'scheduled',
            Appointment.date >= start_date,
            Appointment.date < start_date + timedelta(days=days)
        ).all()
        if appointments:
            logger.warning(f"Cannot delete schedules for doctor_id={doctor_id}; {len(appointments)} scheduled appointments found.")
            raise ValueError(f"Cannot delete schedules; {len(appointments)} scheduled appointments exist.")
        
        DoctorSchedule.query.filter(
            DoctorSchedule.doctor_id == doctor_id,
            DoctorSchedule.start_time >= start_date,
            DoctorSchedule.start_time < start_date + timedelta(days=days)
        ).delete()
        db.session.commit()
        logger.info(f"Deleted existing schedules for doctor_id={doctor_id} from {start_date} for {days} days")
    
    slot_duration = timedelta(minutes=slot_duration)
    
    for day in range(days):
        current_date = start_date + timedelta(days=day)
        if skip_weekends and current_date.weekday() >= 5:
            continue
        current_time = current_date.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        end_time = current_date.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        
        while current_time + slot_duration <= end_time:
            existing_schedule = DoctorSchedule.query.filter(
                DoctorSchedule.doctor_id == doctor_id,
                DoctorSchedule.start_time == current_time
            ).first()
            
            if not existing_schedule:
                new_schedule = DoctorSchedule(
                    doctor_id=doctor_id,
                    start_time=current_time,
                    end_time=current_time + slot_duration,
                    is_available=True
                )
                db.session.add(new_schedule)
            
            current_time += slot_duration
    
    db.session.commit()
    count = DoctorSchedule.query.filter(
        DoctorSchedule.doctor_id == doctor_id,
        DoctorSchedule.start_time >= start_date,
        DoctorSchedule.start_time < start_date + timedelta(days=days),
        DoctorSchedule.is_available == True
    ).count()
    logger.info(f"Generated {count} schedules for doctor_id={doctor_id}")