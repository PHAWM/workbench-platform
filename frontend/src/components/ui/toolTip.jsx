import * as TooltipPrimitive from '@radix-ui/react-tooltip';
import {Info} from 'lucide-react';

export function Tooltip({ children, content, side = "top" }) {
  return (
    <TooltipPrimitive.Root>
      <TooltipPrimitive.Trigger asChild>
        {children}
      </TooltipPrimitive.Trigger>
      
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content 
          side={side}
          sideOffset={5}
          className="z-50 bg-purple-100 border-2 border-purple-100 text-base px-2 py-1 rounded animate-in fade-in"
        >
          {content}
          <TooltipPrimitive.Arrow className="fill-black" />
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}

export function InfoTooltip({ content, side="right"}) {
  return (
    <Tooltip content={content} side={side}>
      {/* Accessibility Note: We wrap the icon in a button so keyboard users 
         can Tab to it and hit Enter/Space to see the tooltip. 
      */}
      <button 
        type="button" 
        className="text-purple-500 hover:text-purple-900 transition-colors cursor-help align-middle"
        aria-label="More information"
      >
        <Info size={20} strokeWidth={3}/> 
      </button>
    </Tooltip>
  );
}