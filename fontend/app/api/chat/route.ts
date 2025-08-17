import { type NextRequest, NextResponse } from "next/server"

export async function POST(request: NextRequest) {
  try {
    // Parse JSON body
    const { message, userId } = await request.json()

    // Validate message presence
    if (!message || typeof message !== "string" || message.trim() === "") {
      return NextResponse.json({ error: "Message is required" }, { status: 400 })
    }

    const chatbotPayload = {
      user_id: userId || "user123",
      message: message.trim(),
    }

    const chatbotResponse = await fetch("https://saloon-chatbot.onrender.com/api/chatbot/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(chatbotPayload),
    })

    if (!chatbotResponse.ok) {
      const errorText = await chatbotResponse.text()
      console.error("Salon chatbot API error:", chatbotResponse.status, errorText)
      throw new Error("Failed to get response from salon chatbot API")
    }

    const data = await chatbotResponse.json()

    if (!data.bot) {
      return NextResponse.json({ error: "No reply received from salon chatbot" }, { status: 502 })
    }

    return NextResponse.json({ reply: data.bot })
  } catch (error) {
    console.error("Error in salon chat API:", error)
    return NextResponse.json({ error: "Failed to process message" }, { status: 500 })
  }
}
