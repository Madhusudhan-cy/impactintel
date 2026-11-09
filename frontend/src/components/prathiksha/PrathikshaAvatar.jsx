import React from 'react';

export default function PrathikshaAvatar({ size = 'md', className = '' }) {
  const sizeMap = {
    xs: 'w-6 h-6',
    sm: 'w-8 h-8',
    md: 'w-10 h-10',
    lg: 'w-14 h-14',
    xl: 'w-18 h-18',
  };

  const dim = sizeMap[size] || sizeMap.md;

  return (
    <div
      className={`relative inline-flex items-center justify-center shrink-0 rounded-xl bg-gradient-to-br from-[#DDF7EF] via-[#BAEFE2] to-[#55BDEB]/30 border border-[#16B89A]/40 shadow-sm select-none ${dim} ${className}`}
      aria-label="Prathiksha Mascot"
    >
      <svg
        viewBox="0 0 48 48"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="w-[85%] h-[85%]"
      >
        {/* Antenna */}
        <path
          d="M24 10V4"
          stroke="#087F70"
          strokeWidth="2.5"
          strokeLinecap="round"
        />
        <circle cx="24" cy="4" r="3" fill="#16B89A" stroke="#087F70" strokeWidth="1.5" />
        <circle cx="24" cy="4" r="1.2" fill="#55BDEB" />

        {/* Robot Head Outer */}
        <rect
          x="7"
          y="10"
          width="34"
          height="28"
          rx="8"
          fill="#FFFFFF"
          stroke="#087F70"
          strokeWidth="2.5"
        />

        {/* Ears */}
        <rect x="3" y="20" width="3" height="8" rx="1.5" fill="#55BDEB" stroke="#087F70" strokeWidth="1.5" />
        <rect x="42" y="20" width="3" height="8" rx="1.5" fill="#55BDEB" stroke="#087F70" strokeWidth="1.5" />

        {/* Screen/Faceplate */}
        <rect
          x="11"
          y="14"
          width="26"
          height="20"
          rx="5"
          fill="#F5FAFA"
          stroke="#CBEAE7"
          strokeWidth="1.5"
        />

        {/* Friendly Happy Eyes */}
        <circle cx="18" cy="22" r="3" fill="#087F70" />
        <circle cx="17.2" cy="21.2" r="1" fill="#FFFFFF" />
        <circle cx="30" cy="22" r="3" fill="#087F70" />
        <circle cx="29.2" cy="21.2" r="1" fill="#FFFFFF" />

        {/* Cheeks */}
        <circle cx="14.5" cy="26" r="1.8" fill="#16B89A" opacity="0.6" />
        <circle cx="33.5" cy="26" r="1.8" fill="#16B89A" opacity="0.6" />

        {/* Warm Doodle Smile */}
        <path
          d="M20.5 27.5C21.8 29.5 26.2 29.5 27.5 27.5"
          stroke="#087F70"
          strokeWidth="2"
          strokeLinecap="round"
        />

        {/* Sparkle badge */}
        <path
          d="M37 12L38 9L41 8L38 7L37 4L36 7L33 8L36 9L37 12Z"
          fill="#55BDEB"
        />
      </svg>
    </div>
  );
}
