"""Deterministic email template renderers based on database models."""

from fieldops.db.models import Appointment, Customer, ServiceRequest, Technician


def render_appointment_confirmation(
    customer: Customer,
    appointment: Appointment,
    service_request: ServiceRequest,
    technician: Technician,
) -> tuple[str, str]:
    """Render appointment confirmation email subject and body strictly from database truth.

    Returns:
        tuple[str, str]: (subject, body)
    """
    start_str = appointment.start_time.isoformat()
    end_str = appointment.end_time.isoformat()
    tech_name = technician.name
    service_type = service_request.service_type
    location = service_request.location
    cust_name = customer.name

    subject = f"Appointment Confirmation #{appointment.id} - {service_type.replace('_', ' ').title()}"

    body = (
        f"Dear {cust_name},\\n\\n"
        f"Your service appointment #{appointment.id} has been confirmed.\\n\\n"
        f"Details:\\n"
        f"- Service Type: {service_type}\\n"
        f"- Assigned Technician: {tech_name}\\n"
        f"- Scheduled Time: {start_str} to {end_str}\\n"
        f"- Service Location: {location}\\n\\n"
        f"Thank you for choosing FieldOps!\\n"
    )
    return subject, body
