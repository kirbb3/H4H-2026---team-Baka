import { useEffect, useState } from "react";

interface ToastProps {
  message: string;
  onDone: () => void;
}

export function Toast({ message, onDone }: ToastProps) {
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    const fadeTimer = setTimeout(() => setLeaving(true), 2200);
    const removeTimer = setTimeout(onDone, 2500);
    return () => {
      clearTimeout(fadeTimer);
      clearTimeout(removeTimer);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div
      style={{ left: "50%", bottom: "2rem" }}
      className={`fixed z-[9999] px-5 py-3 bg-gray-700 text-white text-sm font-medium rounded-xl shadow-xl pointer-events-none ${
        leaving ? "animate-toast-out" : "animate-toast-in"
      }`}
    >
      {message}
    </div>
  );
}
