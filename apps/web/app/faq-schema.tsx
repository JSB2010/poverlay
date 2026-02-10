export function FAQSchema() {
  const faqSchema = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: [
      {
        '@type': 'Question',
        name: 'What is POVerlay?',
        acceptedAnswer: {
          '@type': 'Answer',
          text: 'POVerlay is a professional GoPro telemetry overlay platform that lets you upload GPX tracks and GoPro clips to create stunning video overlays with real-time speed, altitude, maps, and telemetry data. Perfect for skiing, cycling, mountain biking, and all action sports.',
        },
      },
      {
        '@type': 'Question',
        name: 'What file formats are supported?',
        acceptedAnswer: {
          '@type': 'Answer',
          text: 'POVerlay supports GPX files for GPS tracks and MP4 video files from GoPro cameras. The platform automatically synchronizes your GPS data with your video footage for accurate telemetry overlays.',
        },
      },
      {
        '@type': 'Question',
        name: 'Can I customize the overlay appearance?',
        acceptedAnswer: {
          '@type': 'Answer',
          text: 'Yes! POVerlay offers six professional color themes and seven unique layout styles. You can customize which telemetry data to display, choose map styles, and adjust the overall look to match your content perfectly.',
        },
      },
      {
        '@type': 'Question',
        name: 'How long does rendering take?',
        acceptedAnswer: {
          '@type': 'Answer',
          text: 'Rendering time depends on video length and quality settings. Most videos render in real-time or faster. You can monitor progress in the studio and download your videos when complete.',
        },
      },
      {
        '@type': 'Question',
        name: 'Is POVerlay free to use?',
        acceptedAnswer: {
          '@type': 'Answer',
          text: 'Yes! POVerlay is a free online tool for creating professional GoPro telemetry overlays. Simply upload your files and start rendering.',
        },
      },
    ],
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(faqSchema) }}
    />
  );
}

