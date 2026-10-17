import { useEffect, useState } from "react";

const TICK_MS = 1000;

export function useElapsedSeconds(running: boolean): number {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    if (!running) {
      setSeconds(0);
      return;
    }
    const timer = setInterval(() => setSeconds((previous) => previous + 1), TICK_MS);
    return () => clearInterval(timer);
  }, [running]);

  return seconds;
}
