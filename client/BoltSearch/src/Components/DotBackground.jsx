import React from "react";

export function DotBackground({children}) {
  return (
    (<div
      className=" w-full dark:bg-black bg-black  dark:bg-dot-white/[0.2] bg-dot-white/[0.2] relative flex items-center justify-center">
      <div
        className="absolute pointer-events-none inset-0 flex items-center justify-center dark:bg-black "></div>
      
        {children}
    </div>)
  );
}
