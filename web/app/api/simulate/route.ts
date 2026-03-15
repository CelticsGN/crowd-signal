import { NextResponse } from "next/server"

const BACKEND_URL = `${process.env.BACKEND_URL ?? "http://localhost:8000"}/api/v1/simulate`

export async function POST(request: Request) {
  let payload: unknown

  try {
    payload = await request.json()
  } catch {
    return NextResponse.json({ error: "Invalid JSON payload." }, { status: 400 })
  }

  try {
    const upstream = await fetch(BACKEND_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
      cache: "no-store",
    })

    const text = await upstream.text()
    let data: unknown
    try {
      data = text ? JSON.parse(text) : {}
    } catch {
      data = { error: "Backend returned a non-JSON response." }
    }

    if (!upstream.ok) {
      return NextResponse.json(
        {
          error: "Simulation backend request failed.",
          details: data,
        },
        { status: upstream.status },
      )
    }

    return NextResponse.json(data, { status: 200 })
  } catch (error) {
    return NextResponse.json(
      {
        error: "Unable to reach simulation backend.",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 502 },
    )
  }
}
