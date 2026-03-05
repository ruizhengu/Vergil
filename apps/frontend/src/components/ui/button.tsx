import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap text-sm font-medium transition-all duration-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--ring))] focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 font-mono",
  {
    variants: {
      variant: {
        default: "bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] hover:bg-[hsl(var(--primary))/0.9]",
        destructive: "bg-[hsl(var(--destructive))] text-[hsl(var(--destructive-foreground))] hover:bg-[hsl(var(--destructive))/0.9]",
        outline: "border border-[hsl(var(--foreground)/0.2)] bg-transparent text-[hsl(var(--foreground))] hover:bg-[hsl(var(--foreground)/0.05)]",
        secondary: "bg-[hsl(var(--secondary))] text-[hsl(var(--secondary-foreground))] hover:bg-[hsl(var(--secondary))/0.8]",
        ghost: "hover:bg-[hsl(var(--accent)/0.1)] hover:text-[hsl(var(--accent-foreground))]",
        link: "text-[hsl(var(--primary))] underline-offset-4 hover:underline",
        capsule: "rounded-full bg-[hsl(var(--card))] border border-[hsl(var(--foreground)/0.1)] text-[hsl(var(--foreground))] hover:border-[hsl(var(--primary))/0.4] hover:shadow-[0_0_20px_hsl(199_90%_64%/0.15)]",
        "capsule-solid": "rounded-full bg-[hsl(var(--foreground))] text-[hsl(var(--background))] hover:bg-[hsl(var(--foreground)/0.9)]",
        "capsule-outline": "rounded-full border border-[hsl(var(--foreground)/0.2)] bg-transparent text-[hsl(var(--foreground))] hover:bg-[hsl(var(--foreground))] hover:text-[hsl(var(--background))]",
        "capsule-gold": "rounded-full border border-[hsl(var(--secondary)/0.4)] bg-transparent text-[hsl(var(--secondary))] hover:bg-[hsl(var(--secondary))] hover:text-[hsl(var(--secondary-foreground))]",
        "capsule-primary": "rounded-full bg-[hsl(var(--primary)/0.1)] border border-[hsl(var(--primary)/0.3)] text-[hsl(var(--primary))] hover:bg-[hsl(var(--primary)/0.2)]",
      },
      size: {
        default: "h-10 px-5 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-12 px-8 text-base",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />;
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
