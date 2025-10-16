from fastapi import FastAPI, Request
from uuid import uuid4
from dotenv import load_dotenv
from openai import AsyncOpenAI
import chainlit as cl
import json
import asyncio
import httpx
import os

load_dotenv()
openaiClient = AsyncOpenAI()

tools = [
    {
        "type": "function",
        "name": "list_all_upcoming_bookings",
        "description": "Get a list of all upcoming bookings.",
        "parameters": {
          "type": "object",
          "properties": {
            "attendeeEmail": {
              "type": "string",
              "description": "The email of the attendee to get bookings for.",
            }
          },
          "required": ["attendeeEmail"],
        },
    },
    {
        "type": "function",
        "name": "create_booking",
        "description": "Create a new booking for a given start time with 30 min duration.",
        "parameters": {
          "type": "object",
          "properties": {
            "attendeeEmail": {
              "type": "string",
              "description": "The email of the attendee to create a booking for.",
            },
            "attendeeName": {
              "type": "string",
              "description": "The name of the attendee to create a booking for.",
            },
            "startTime": {
              "type": "string",
              "description": "The start time of the booking in ISO 8601 format in UTC timezone (e.g., 2023-10-01T00:00:00Z).",
            },
            "timeZone": {
              "type": "string",
              "description": "The time zone of the attendee (e.g., America/New_York).",
            },
            "phoneNumber": {
              "type": "string",
              "description": "The phone number of the attendee (optional).",
            },
          },
          "required": ["attendeeEmail", "attendeeName", "startTime", "timeZone"],
        },
    },
    {
        "type": "function",
        "name": "look_up_first_booking",
        "description": "Look up the first booking for a given email after a specified start time.",
        "parameters": {
          "type": "object",
          "properties": {
            "attendeeEmail": {
              "type": "string",
              "description": "The email of the attendee to get bookings for.",
            },
            "scheduledStartTime": {
              "type": "string",
              "description": "The scheduled start time to look for bookings after, in ISO 8601 format in UTC timezone (e.g., 2023-10-01T00:00:00Z).",
            }
          },
          "required": ["attendeeEmail", "scheduledStartTime"],
        },
    },
    {
        "type": "function",
        "name": "cancel_first_booking",
        "description": "Cancel the first booking for a given email after a specified start time.",
        "parameters": {
          "type": "object",
          "properties": {
            "attendeeEmail": {
              "type": "string",
              "description": "The email of the attendee to cancel the booking for.",
            },
            "scheduledStartTime": {
              "type": "string",
              "description": "The scheduled start time to look for bookings after, in ISO 8601 format in UTC timezone (e.g., 2023-10-01T00:00:00Z).",
            },
          },
          "required": ["attendeeEmail", "scheduledStartTime"],
        },
    },
    {
        "type": "function",
        "name": "reschedule_first_booking",
        "description": "Reschedule the first booking for a given email after a specified start time to a new start time.",
        "parameters": {
          "type": "object",
          "properties": {
            "attendeeEmail": {
              "type": "string",
              "description": "The email of the attendee to reschedule the booking for.",
            },
            "scheduledStartTime": {
              "type": "string",
              "description": "The scheduled start time to look for bookings after, in ISO 8601 format in UTC timezone (e.g., 2023-10-01T00:00:00Z).",
            },
            "newStartTime": {
              "type": "string",
              "description": "The new start time for the booking in ISO 8601 format in UTC timezone (e.g., 2023-10-01T00:00:00Z).",
            },
          },
          "required": ["attendeeEmail", "scheduledStartTime", "newStartTime"],
        },
    }
]

calApiHeaders = {
    "Authorization": f"Bearer {os.getenv('CAL_API_KEY')}",
    "cal-api-version": "2024-08-13",
    "Content-Type": "application/json"
}

async def list_all_upcoming_bookings(chatList, callId, attendeeEmail):
    url = "https://api.cal.com/v2/bookings"
    params = {
        "status": "upcoming",
        "attendeeEmail": attendeeEmail,
    }
    async with httpx.AsyncClient() as httpClient:
      response = await httpClient.get(url, headers=calApiHeaders, params=params)
      bookings = response.json()
    chatList.append({
        "type": "function_call_output",
        "call_id": callId,
        "output": json.dumps(bookings)
    })

async def create_booking(chatList, callId, attendeeEmail, attendeeName, startTime, timeZone, phoneNumber=None):
    url = "https://api.cal.com/v2/bookings"
    data = {
        "attendee": {
          "name": attendeeName,
          "email": attendeeEmail,
          "timeZone": timeZone,
          "phoneNumber": phoneNumber,
        },
        "start": startTime,
        "eventTypeId": 3666489,
    }
    async with httpx.AsyncClient() as httpClient:
      response = await httpClient.post(url, headers=calApiHeaders, json=data)
      booking = response.json()
    chatList.append({
        "type": "function_call_output",
        "call_id": callId,
        "output": json.dumps(booking)
    })

async def look_up_first_booking(chatList, callId, attendeeEmail, scheduledStartTime):
    url = "https://api.cal.com/v2/bookings"
    params = {
        "status": "upcoming",
        "attendeeEmail": attendeeEmail,
        "afterStart": scheduledStartTime,
        "take": 1,
    }
    async with httpx.AsyncClient() as httpClient:
      response = await httpClient.get(url, headers=calApiHeaders, params=params)
      bookings = response.json()
    chatList.append({
        "type": "function_call_output",
        "call_id": callId,
        "output": json.dumps(bookings)
    })

async def cancel_first_booking(chatList, callId, attendeeEmail, scheduledStartTime):
    # First, look up the first booking
    url = "https://api.cal.com/v2/bookings"
    params = {
        "status": "upcoming",
        "attendeeEmail": attendeeEmail,
        "afterStart": scheduledStartTime,
        "take": 1,
    }
    async with httpx.AsyncClient() as httpClient:
      response = await httpClient.get(url, headers=calApiHeaders, params=params)
      bookings = response.json()
    if len(bookings["data"]) == 0:
      chatList.append({
          "type": "function_call_output",
          "call_id": callId,
          "output": json.dumps(bookings)
      })
      return

    bookingUid = bookings["data"][0]["uid"]
    cancel_url = f"https://api.cal.com/v2/bookings/{bookingUid}/cancel"
    params = {
        "cancellationReason": "Cancelled by user request via chat bot.",
    }
    async with httpx.AsyncClient() as httpClient:
      response = await httpClient.post(cancel_url, headers=calApiHeaders, json=params)
      cancellationResult = response.json()
    chatList.append({
        "type": "function_call_output",
        "call_id": callId,
        "output": json.dumps(cancellationResult)
    })

async def reschedule_first_booking(chatList, callId, attendeeEmail, scheduledStartTime, newStartTime):
    # First, look up the first booking
    url = "https://api.cal.com/v2/bookings"
    params = {
        "status": "upcoming",
        "attendeeEmail": attendeeEmail,
        "afterStart": scheduledStartTime,
        "take": 1,
    }
    async with httpx.AsyncClient() as httpClient:
      response = await httpClient.get(url, headers=calApiHeaders, params=params)
      bookings = response.json()
    if len(bookings["data"]) == 0:
      chatList.append({
          "type": "function_call_output",
          "call_id": callId,
          "output": json.dumps(bookings)
      })
      return

    bookingUid = bookings["data"][0]["uid"]
    reschedule_url = f"https://api.cal.com/v2/bookings/{bookingUid}/reschedule"
    data = {
        "start": newStartTime,
        "reschedulingReason": "User requested reschedule",
    }
    async with httpx.AsyncClient() as httpClient:
      response = await httpClient.post(reschedule_url, headers=calApiHeaders, json=data)
      rescheduleResult = response.json()
    chatList.append({
        "type": "function_call_output",
        "call_id": callId,
        "output": json.dumps(rescheduleResult)
    })

sessions = {}

@cl.on_chat_start
async def on_start():
  await cl.Message(content="Hi! I can help you with your calendar bookings!").send()

@cl.on_message
async def on_message(message: cl.Message):
  sessionId = cl.user_session.get("id")  # auto unique session id
  if sessionId not in sessions:
    sessions[sessionId] = {"chatList": []}
  session = sessions[sessionId]
  chatList = session["chatList"]
  chatList.append({"role": "user", "content": message.content})

  while True:
    response = await openaiClient.responses.create(
      model="gpt-5",
      tools=tools,
      instructions="You are a helpful assistant that helps people manage their calendar bookings. You can call functions to list, create, cancel, and reschedule bookings as needed. If information is missing, ask the user for more details before calling a function. Before cancelling or rescheduling a booking, make sure to get confirm the booking details with the user. If you have provided a final response to the user, stop and do not call any more functions.",
      input=chatList,
    )
    chatList += response.output

    function_call_found = False
    for item in response.output:
      if item.type == "function_call":
        function_call_found = True
        if item.name == "list_all_upcoming_bookings":
          args = json.loads(item.arguments)
          await list_all_upcoming_bookings(chatList, item.call_id, **args)
        elif item.name == "create_booking":
          args = json.loads(item.arguments)
          await create_booking(chatList, item.call_id, **args)
        elif item.name == "look_up_first_booking":
          args = json.loads(item.arguments)
          await look_up_first_booking(chatList, item.call_id, **args)
        elif item.name == "cancel_first_booking":
          args = json.loads(item.arguments)
          await cancel_first_booking(chatList, item.call_id, **args)
        elif item.name == "reschedule_first_booking":
          args = json.loads(item.arguments)
          await reschedule_first_booking(chatList, item.call_id, **args)
    if not function_call_found:
      responseText = response.output_text
      break
  print("chats:", chatList)
  await cl.Message(content=responseText).send()
