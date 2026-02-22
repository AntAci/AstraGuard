import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import MissionControl from './MissionControl'
import Hero from './components/Hero'
import { AuthGate } from './auth/AuthGate'

export default function App() {
    return (
        <Router>
            <Routes>
                <Route path="/" element={<Hero />} />
                <Route
                    path="/app"
                    element={
                        <AuthGate>
                            <MissionControl />
                        </AuthGate>
                    }
                />
            </Routes>
        </Router>
    )
}
