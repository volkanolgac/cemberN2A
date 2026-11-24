import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.cember.game',
  appName: 'ÇEMBER',
  webDir: 'dist',
  backgroundColor: '#0B0F19',
  ios: {
    contentInset: 'never',
    scrollEnabled: false, // no rubber-band bounce during play
    allowsLinkPreview: false,
  },
  plugins: {
    SplashScreen: { launchShowDuration: 800, backgroundColor: '#0B0F19', showSpinner: false },
    // Hides the status bar and the home indicator (Capacitor 8 built-in plugin)
    SystemBars: { hidden: true },
  },
};

export default config;
