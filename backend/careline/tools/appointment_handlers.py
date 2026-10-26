from __future__ import annotations

import asyncio
from typing import Callable

from pipecat.services.llm_service import FunctionCallParams

from backend.careline.tools.appointments import AppointmentTools


def make_appointment_tools(service: AppointmentTools) -> list[Callable]:
    async def check_available_slots(params: FunctionCallParams, date: str) -> None:
        """Check the clinic's open appointment times for a date.

        Args:
            date: Clinic-local date in YYYY-MM-DD format. Always check before offering a time.
        """
        result = await asyncio.to_thread(service.check_available_slots, date)
        await params.result_callback(result)

    async def book_appointment(
        params: FunctionCallParams,
        date: str,
        time: str,
        patient_name: str,
        caller_confirmed: bool,
    ) -> None:
        """Book a checked appointment only after explicit caller confirmation.

        Args:
            date: The confirmed clinic-local appointment date in YYYY-MM-DD format.
            time: The confirmed clinic-local time in 24-hour HH:MM format.
            patient_name: The caller-provided name to put on this new appointment.
            caller_confirmed: True only after confirming the exact patient name, date, and time aloud and getting the caller's agreement.
        """
        result = await asyncio.to_thread(
            service.book_appointment, date, time, patient_name, caller_confirmed
        )
        await params.result_callback(result)

    async def reschedule_appointment(
        params: FunctionCallParams,
        reference_code: str,
        patient_name: str,
        new_date: str,
        new_time: str,
    ) -> None:
        """Move an appointment after verifying the caller's booking reference and name.

        Args:
            reference_code: The booking reference the caller received when the appointment was created.
            patient_name: The caller-provided name associated with the appointment.
            new_date: The requested new clinic-local date in YYYY-MM-DD format.
            new_time: The requested new clinic-local time in 24-hour HH:MM format.
        """
        result = await asyncio.to_thread(
            service.reschedule_appointment,
            reference_code,
            patient_name,
            new_date,
            new_time,
        )
        await params.result_callback(result)

    async def cancel_appointment(
        params: FunctionCallParams, reference_code: str, patient_name: str
    ) -> None:
        """Cancel the caller's appointment after verifying reference and name.

        Args:
            reference_code: The booking reference the caller received when the appointment was created.
            patient_name: The caller-provided name associated with the appointment.
        """
        result = await asyncio.to_thread(
            service.cancel_appointment, reference_code, patient_name
        )
        await params.result_callback(result)

    return [check_available_slots, book_appointment, reschedule_appointment, cancel_appointment]
