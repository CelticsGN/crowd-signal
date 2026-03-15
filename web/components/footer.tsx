"use client"

import { motion } from "framer-motion"

const ease = [0.22, 1, 0.36, 1] as const

export function Footer() {
  return (
    <motion.footer
      initial={{ opacity: 0 }}
      whileInView={{ opacity: 1 }}
      viewport={{ once: true, margin: "-40px" }}
      transition={{ duration: 0.6, ease }}
      className="w-full border-t-2 border-foreground px-6 py-8 lg:px-12"
    >
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div className="flex flex-col gap-1">
          <span className="text-xs font-mono tracking-[0.15em] uppercase font-bold text-foreground">
            CROWD.SIGNAL
          </span>
          <span className="text-[10px] font-mono tracking-widest text-muted-foreground">
            {"(C) 2026 CROWD SIGNAL PROJECT - MVP - ACTIVELY BUILDING"}
          </span>
          <span className="text-[10px] font-mono tracking-widest text-muted-foreground">
            {"Built by "}
            <a
              href="https://www.linkedin.com/in/nihaallp/"
              target="_blank"
              rel="noreferrer"
              className="underline hover:text-foreground"
            >
              Nihal Pardeshi
            </a>
            {" and "}
            <a
              href="https://www.linkedin.com/in/gaurav-guddeti-a2359827b/"
              target="_blank"
              rel="noreferrer"
              className="underline hover:text-foreground"
            >
              Gaurav Guddeti
            </a>
          </span>
        </div>
        <div className="flex items-center gap-6">
          {[
            { label: "Privacy", href: "#" },
            { label: "Terms", href: "#" },
            { label: "Status", href: "#" },
            { label: "GitHub", href: "https://github.com/NihaallX/crowd-signal" },
          ].map((link, i) => (
            <motion.a
              key={link.label}
              href={link.href}
              target={link.href.startsWith("http") ? "_blank" : undefined}
              rel={link.href.startsWith("http") ? "noreferrer" : undefined}
              initial={{ opacity: 0, y: 6 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.1 + i * 0.06, duration: 0.4, ease }}
              className="text-[10px] font-mono tracking-widest uppercase text-muted-foreground hover:text-foreground transition-colors duration-200"
            >
              {link.label}
            </motion.a>
          ))}
        </div>
      </div>
    </motion.footer>
  )
}
