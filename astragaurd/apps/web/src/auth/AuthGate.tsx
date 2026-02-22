import { useCallback, useEffect, useMemo, useState } from "react";
import { useWallet } from "@solana/wallet-adapter-react";
import { WalletMultiButton } from "@solana/wallet-adapter-react-ui";

function toBase64(bytes: Uint8Array) {
    return btoa(String.fromCharCode(...bytes));
}

export function AuthGate({ children }: { children: React.ReactNode }) {
    const { publicKey, connected, signMessage } = useWallet();
    const [authed, setAuthed] = useState(false);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const storageKey = useMemo(
        () => (publicKey ? `astragaurd_auth_${publicKey.toBase58()}` : null),
        [publicKey]
    );

    useEffect(() => {
        setError(null);
        if (!storageKey) {
            setAuthed(false);
            return;
        }
        setAuthed(localStorage.getItem(storageKey) === "1");
    }, [storageKey]);

    const handleSignIn = useCallback(async () => {
        setError(null);

        if (!connected || !publicKey) {
            setError("Connect your wallet to continue.");
            return;
        }
        if (!signMessage) {
            setError("Wallet does not support message signing.");
            return;
        }

        setBusy(true);
        try {
            const nonce = crypto.getRandomValues(new Uint32Array(1))[0].toString(16);
            const issuedAt = new Date().toISOString();

            const message = `AstraGuard Sign-In
Domain: localhost
Wallet: ${publicKey.toBase58()}
Nonce: ${nonce}
Issued At: ${issuedAt}`;

            const encoded = new TextEncoder().encode(message);
            const signature = await signMessage(encoded);

            localStorage.setItem(storageKey!, "1");
            localStorage.setItem(`${storageKey!}_msg`, message);
            localStorage.setItem(`${storageKey!}_sig`, toBase64(signature));

            setAuthed(true);
        } catch (e: any) {
            setError(e?.message ?? "Signature rejected.");
        } finally {
            setBusy(false);
        }
    }, [connected, publicKey, signMessage, storageKey]);

    const handleSignOut = useCallback(() => {
        if (!storageKey) return;
        localStorage.removeItem(storageKey);
        localStorage.removeItem(`${storageKey}_msg`);
        localStorage.removeItem(`${storageKey}_sig`);
        setAuthed(false);
    }, [storageKey]);

    if (!authed) {
        return (
            <div
                style={{
                    minHeight: "100vh",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    padding: "24px",
                    background: "linear-gradient(180deg, #050610 0%, #0a0e18 100%)",
                }}
            >
                {/* Animated grid behind */}
                <div
                    className="animated-grid"
                    style={{ position: "absolute", inset: 0, opacity: 0.5 }}
                />

                <div
                    style={{
                        position: "relative",
                        zIndex: 10,
                        width: "100%",
                        maxWidth: 440,
                        borderRadius: 16,
                        border: "1px solid rgba(25, 247, 166, 0.15)",
                        background: "rgba(10, 14, 24, 0.85)",
                        backdropFilter: "blur(20px)",
                        padding: "32px",
                        boxShadow: "0 20px 60px rgba(0, 0, 0, 0.6), 0 0 40px rgba(25, 247, 166, 0.05)",
                    }}
                >
                    <div
                        style={{
                            marginBottom: 8,
                            fontSize: 10,
                            letterSpacing: "0.25em",
                            textTransform: "uppercase",
                            color: "rgba(25, 247, 166, 0.7)",
                            fontFamily: "'IBM Plex Mono', monospace",
                        }}
                    >
                        ● Mission Control Access
                    </div>
                    <h2
                        style={{
                            fontSize: 24,
                            fontWeight: 700,
                            color: "#e7f0ff",
                            fontFamily: "'IBM Plex Sans Condensed', sans-serif",
                            margin: 0,
                        }}
                    >
                        Sign in with Solana
                    </h2>
                    <p
                        style={{
                            marginTop: 10,
                            fontSize: 13,
                            lineHeight: 1.6,
                            color: "rgba(231, 240, 255, 0.55)",
                            fontFamily: "'IBM Plex Mono', monospace",
                        }}
                    >
                        Connect your wallet and sign a message to verify operator identity.
                        No transaction, no gas.
                    </p>

                    <div
                        style={{
                            marginTop: 24,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            gap: 12,
                        }}
                    >
                        <WalletMultiButton
                            style={{
                                background: "rgba(25, 247, 166, 0.12)",
                                color: "#19f7a6",
                                border: "1px solid rgba(25, 247, 166, 0.25)",
                                borderRadius: 10,
                                height: 44,
                                fontSize: 13,
                                fontFamily: "'IBM Plex Mono', monospace",
                                fontWeight: 600,
                                letterSpacing: "0.04em",
                            }}
                        />
                        <button
                            onClick={handleSignIn}
                            disabled={!connected || busy}
                            style={{
                                height: 44,
                                padding: "0 20px",
                                borderRadius: 10,
                                background: connected ? "#19f7a6" : "rgba(25, 247, 166, 0.2)",
                                color: "#050610",
                                fontWeight: 700,
                                fontSize: 13,
                                fontFamily: "'IBM Plex Sans Condensed', sans-serif",
                                letterSpacing: "0.06em",
                                textTransform: "uppercase",
                                border: "none",
                                cursor: connected && !busy ? "pointer" : "not-allowed",
                                opacity: !connected || busy ? 0.45 : 1,
                                transition: "all 0.2s ease",
                            }}
                        >
                            {busy ? "Signing…" : "Sign In"}
                        </button>
                    </div>

                    {error && (
                        <div
                            style={{
                                marginTop: 16,
                                fontSize: 13,
                                color: "#ff6b8a",
                                fontFamily: "'IBM Plex Mono', monospace",
                            }}
                        >
                            {error}
                        </div>
                    )}

                    <div
                        style={{
                            marginTop: 20,
                            fontSize: 11,
                            color: "rgba(231, 240, 255, 0.3)",
                            fontFamily: "'IBM Plex Mono', monospace",
                            lineHeight: 1.5,
                        }}
                    >
                        Demo mode: stores a signed proof locally. In production, signatures
                        are verified server-side with nonce + session tokens.
                    </div>
                </div>
            </div>
        );
    }

    return (
        <>
            <div
                style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "flex-end",
                    padding: "8px 16px",
                    background: "transparent",
                    position: "absolute",
                    top: 0,
                    right: 0,
                    zIndex: 50,
                }}
            >
                <button
                    onClick={handleSignOut}
                    style={{
                        fontSize: 11,
                        color: "rgba(75, 97, 123, 0.7)",
                        background: "none",
                        border: "none",
                        cursor: "pointer",
                        fontFamily: "'IBM Plex Mono', monospace",
                        letterSpacing: "0.06em",
                    }}
                >
                    Sign out
                </button>
            </div>
            {children}
        </>
    );
}
