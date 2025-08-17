import { SalonChatWidget } from "@/components/salon-chat-widget"

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-pink-50 to-purple-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="text-center">
            <h1 className="text-4xl font-bold text-gray-900 mb-2">FIDDEN Salon</h1>
            <p className="text-lg text-gray-600">Premium Hair & Beauty Services</p>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="text-center mb-12">
          <h2 className="text-3xl font-bold text-gray-900 mb-4">Book Your Appointment</h2>
          <p className="text-xl text-gray-600 mb-8">
            Chat with our AI assistant to schedule your perfect salon experience
          </p>
        </div>

        {/* Services Grid */}
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
          <div className="bg-white rounded-lg shadow-md p-6 text-center hover:shadow-lg transition-shadow">
            <div className="w-16 h-16 bg-pink-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <span className="text-2xl">✂️</span>
            </div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2">Haircut</h3>
            <p className="text-gray-600 mb-2">Professional styling and cuts</p>
            <p className="text-2xl font-bold text-pink-600">$25</p>
          </div>

          <div className="bg-white rounded-lg shadow-md p-6 text-center hover:shadow-lg transition-shadow">
            <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <span className="text-2xl">🧔</span>
            </div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2">Beard</h3>
            <p className="text-gray-600 mb-2">Beard trimming and styling</p>
            <p className="text-2xl font-bold text-blue-600">$15</p>
          </div>

          <div className="bg-white rounded-lg shadow-md p-6 text-center hover:shadow-lg transition-shadow">
            <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <span className="text-2xl">✨</span>
            </div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2">Facial</h3>
            <p className="text-gray-600 mb-2">Rejuvenating facial treatments</p>
            <p className="text-2xl font-bold text-green-600">$40</p>
          </div>

          <div className="bg-white rounded-lg shadow-md p-6 text-center hover:shadow-lg transition-shadow">
            <div className="w-16 h-16 bg-purple-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <span className="text-2xl">🛁</span>
            </div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2">SPA</h3>
            <p className="text-gray-600 mb-2">Relaxing spa treatments</p>
            <p className="text-2xl font-bold text-purple-600">$60</p>
          </div>
        </div>

        {/* Call to Action */}
        <div className="text-center">
          <div className="bg-white rounded-lg shadow-md p-8 max-w-2xl mx-auto">
            <h3 className="text-2xl font-bold text-gray-900 mb-4">Ready to Book?</h3>
            <p className="text-gray-600 mb-6">
              Click the chat button in the bottom right corner to start booking your appointment with our AI assistant.
            </p>
            <div className="flex justify-center items-center gap-2 text-sm text-gray-500">
              <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
              <span>AI Assistant Available 24/7</span>
            </div>
          </div>
        </div>
      </main>

      {/* Chat Widget */}
      <SalonChatWidget />
    </div>
  )
}
