import { useEffect, useState } from "react";
import { motion } from "motion/react";


const poems = [
  "山有木兮木有枝，心悦君兮君不知。",
  "人生若只如初见，何事秋风悲画扇。",
  "曾经沧海难为水，除却巫山不是云。",
  "落霞与孤鹜齐飞，秋水共长天一色。",
  "行到水穷处，坐看云起时。",
  "采菊东篱下，悠然见南山。",
  "大漠孤烟直，长河落日圆。",
  "海内存知己，天涯若比邻。",
  "长风破浪会有时，直挂云帆济沧海。",
  "但愿人长久，千里共婵娟。",
  "世事一场大梦，人生几度秋凉。",
  "浮生若梦，为欢几何。",
];

const socialLinks = [
  {
    name: "GitHub",
    href: "https://github.com",
    icon: (
      <svg viewBox="0 0 24 24" fill="currentColor" className="h-[18px] w-[18px]">
        <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
      </svg>
    ),
  },
  {
    name: "Telegram",
    href: "https://t.me",
    icon: (
      <svg viewBox="0 0 24 24" fill="currentColor" className="h-[18px] w-[18px]">
        <path d="M11.944 0A12 12 0 000 12a12 12 0 0012 12 12 12 0 0012-12A12 12 0 0012 0a12 12 0 00-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 01.171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" />
      </svg>
    ),
  },
  {
    name: "X",
    href: "https://x.com",
    icon: (
      <svg viewBox="0 0 24 24" fill="currentColor" className="h-[18px] w-[18px]">
        <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
      </svg>
    ),
  },
  {
    name: "网易云音乐",
    href: "https://music.163.com",
    icon: (
      <svg viewBox="0 0 24 24" fill="currentColor" className="h-[18px] w-[18px]">
        <path d="M12 0C5.372 0 0 5.372 0 12s5.372 12 12 12 12-5.372 12-12S18.628 0 12 0zm5.92 17.108c-.745 1.222-1.86 2.068-3.327 2.528-1.378.43-2.71.404-3.996-.08a5.07 5.07 0 01-2.715-2.244c-.674-1.166-.796-2.418-.364-3.746.336-1.032.893-1.907 1.671-2.62.81-.742 1.756-1.207 2.834-1.393.332-.058.666-.076 1-.054.51.034.924.267 1.242.684.318.418.45.895.394 1.43a2.38 2.38 0 01-.564 1.282c-.37.436-.856.7-1.46.792-.39.06-.773.032-1.15-.084a1.474 1.474 0 01-.923-.782c-.11-.228-.15-.472-.122-.73.04-.356.186-.654.44-.894.046-.044.094-.086.144-.126l.11-.086c.07-.05.078-.09.024-.12-.12-.066-.252-.078-.396-.034-.36.11-.648.336-.864.678-.328.52-.408 1.08-.24 1.682.2.718.626 1.24 1.278 1.566.754.378 1.548.434 2.382.17a3.823 3.823 0 002.172-1.75c.43-.796.572-1.648.424-2.554-.19-1.174-.74-2.138-1.648-2.89a5.1 5.1 0 00-2.83-1.188c-1.136-.134-2.216.05-3.242.55-1.322.646-2.27 1.636-2.842 2.97-.442 1.028-.58 2.1-.416 3.216.21 1.42.848 2.614 1.912 3.582 1.128 1.028 2.47 1.598 4.024 1.712.37.028.74.018 1.11-.028.168-.02.266.044.294.192.018.1-.02.178-.114.234-.118.07-.248.112-.388.124-.64.058-1.274.04-1.9-.054z" />
      </svg>
    ),
  },
];

const HeroContent = () => {
  const [poem, setPoem] = useState(() => poems[Math.floor(Math.random() * poems.length)]);
  const [flipped, setFlipped] = useState(false);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setPoem((current) => {
        const candidates = poems.filter((item) => item !== current);
        return candidates[Math.floor(Math.random() * candidates.length)];
      });
    }, 8000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <section className="flex-1 flex flex-col px-6 lg:px-16">
      {/* Centered content */}
      <div className="flex flex-1 flex-col items-center justify-center gap-8">
        {/* Coin — click to flip between name & avatar */}
        <motion.div
          className="cursor-pointer select-none"
          style={{ perspective: 1000 }}
          onClick={() => setFlipped((f) => !f)}
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
        >
          <motion.div
            className="relative h-48 w-48 sm:h-56 sm:w-56"
            animate={{ rotateY: flipped ? 180 : 0 }}
            transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
            style={{ transformStyle: "preserve-3d" }}
          >
            {/* Front — Name */}
            <div
              className="absolute inset-0 rounded-full"
              style={{ backfaceVisibility: "hidden" }}
            >
              <div className="h-full w-full rounded-full liquid-glass-coin flex items-center justify-center">
                <span
                  className="text-5xl sm:text-6xl text-white select-none"
                  style={{ fontFamily: "'Pinyon Script', cursive" }}
                >
                  Felix
                </span>
              </div>
            </div>

            {/* Back — Avatar */}
            <div
              className="absolute inset-0 rounded-full"
              style={{ backfaceVisibility: "hidden", transform: "rotateY(180deg)" }}
            >
              <div className="h-full w-full rounded-full overflow-hidden liquid-glass-coin">
                <img
                  src="/images/avatar.png"
                  alt="Felix"
                  className="h-full w-full object-cover"
                />
              </div>
            </div>
          </motion.div>
        </motion.div>

        {/* Bio */}
        <motion.p
          className="max-w-[26rem] text-center text-base leading-7 text-white/55 sm:text-lg"
          style={{ fontFamily: "'Instrument Serif', serif" }}
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
        >
          我做网页设计，也写前端，把视觉、节奏、内容和交互整理成一个自然流动的个人空间。
        </motion.p>

        {/* Social icons */}
        <motion.div
          className="flex flex-wrap justify-center gap-3"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.18, ease: [0.16, 1, 0.3, 1] }}
        >
          {socialLinks.map((link) => (
            <a
              key={link.name}
              href={link.href}
              target="_blank"
              rel="noopener noreferrer"
              title={link.name}
              className="flex h-10 w-10 items-center justify-center rounded-full liquid-glass text-white/60 transition-colors duration-200 hover:text-white active:scale-95"
            >
              {link.icon}
            </a>
          ))}
        </motion.div>

        {/* CTA buttons — icon-only, expand on hover */}
        <motion.div
          className="flex flex-wrap justify-center gap-3"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.24, ease: [0.16, 1, 0.3, 1] }}
        >
          <a
            href="/resume"
            className="group flex h-10 items-center justify-center rounded-full liquid-glass text-white/60 hover:text-white transition-all duration-300 ease-out w-10 hover:w-[6.5rem] active:scale-[0.97] overflow-hidden"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="h-[18px] w-[18px] shrink-0">
              <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <span className="max-w-0 overflow-hidden group-hover:max-w-[4rem] transition-all duration-300 ease-out whitespace-nowrap text-sm font-body font-medium opacity-0 group-hover:opacity-100 group-hover:ml-1.5">
              简历
            </span>
          </a>
          <a
            href="/guestbook"
            className="group flex h-10 items-center justify-center rounded-full liquid-glass text-white/60 hover:text-white transition-all duration-300 ease-out w-10 hover:w-[7rem] active:scale-[0.97] overflow-hidden"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="h-[18px] w-[18px] shrink-0">
              <path d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <span className="max-w-0 overflow-hidden group-hover:max-w-[4rem] transition-all duration-300 ease-out whitespace-nowrap text-sm font-body font-medium opacity-0 group-hover:opacity-100 group-hover:ml-1.5">
              留言板
            </span>
          </a>
        </motion.div>
      </div>

      {/* Bottom poem + scroll hint */}
      <motion.div
        className="flex flex-col items-center gap-3 pb-6 pt-2"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.55, delay: 0.24, ease: [0.16, 1, 0.3, 1] }}
      >
        <p className="max-w-[44rem] text-center text-sm leading-6 text-white/34 sm:text-[0.95rem]">
          {poem}
        </p>
        <svg
          className="h-5 w-5 text-white/20 animate-bounce"
          style={{ animationDuration: "2s" }}
          viewBox="0 0 20 20"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.5}
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M4 7l6 6 6-6" />
        </svg>
      </motion.div>
    </section>
  );
};

export default HeroContent;
